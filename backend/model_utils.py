import os
import json
import numpy as np
import tensorflow as tf
from PIL import Image
import threading
import ssl

# Bypass SSL certificate verification for macOS Keras downloads
ssl._create_default_https_context = ssl._create_unverified_context

# Paths
CLASSIFIER_PATH = 'models/face_classifier.keras'
CLASS_MAPPING_PATH = 'data/class_mapping.json'
FACES_DIR = 'data/faces'
FEATURE_CACHE_PATH = 'data/feature_cache.npz'  # Cached MobileNetV2 embeddings

# Locks for thread safety in FastAPI
model_lock = threading.RLock()

# Global TensorFlow session models
_base_model = None
_classifier_model = None
_class_mapping = None
_inverse_class_mapping = None

def get_base_model():
    """Lazy-load the MobileNetV2 feature extractor."""
    global _base_model
    if _base_model is None:
        with model_lock:
            if _base_model is None:
                print("Loading MobileNetV2 base feature extractor...")
                # MobileNetV2 pre-trained on ImageNet, without final classification layers
                _base_model = tf.keras.applications.MobileNetV2(
                    weights='imagenet',
                    include_top=False,
                    pooling='avg',
                    input_shape=(224, 224, 3)
                )
                print("MobileNetV2 base feature extractor loaded successfully.")
    return _base_model

def preprocess_face(face_img):
    """
    Preprocess face image for MobileNetV2.
    face_img: numpy array of shape (H, W, 3) in BGR format (from OpenCV)
    Returns: preprocessed batch tensor of shape (1, 224, 224, 3)
    """
    # Convert OpenCV BGR to PIL RGB
    rgb_img = Image.fromarray(face_img[:, :, ::-1])
    # Resize to MobileNet standard 224x224
    rgb_img = rgb_img.resize((224, 224))
    img_array = np.array(rgb_img, dtype=np.float32)
    # Expand dims to batch size 1: (1, 224, 224, 3)
    img_batch = np.expand_dims(img_array, axis=0)
    # Scale pixels to [-1, 1] range as expected by MobileNetV2
    return tf.keras.applications.mobilenet_v2.preprocess_input(img_batch)

def extract_features(face_img):
    """Extract a 1280-dimensional feature vector for a face crop."""
    base_model = get_base_model()
    preprocessed = preprocess_face(face_img)
    # Run feature extraction
    features = base_model(preprocessed, training=False)
    return features.numpy()[0]  # Shape: (1280,)

def load_dataset():
    """
    Load all registered face images and construct training arrays.
    Uses a feature cache (.npz) to avoid re-extracting MobileNetV2 embeddings
    for images that were already processed, dramatically speeding up re-training.
    Returns: X (features), y (labels), classes (class list)
    """
    os.makedirs('data', exist_ok=True)

    # Ensure FACES_DIR and unknown directory exist
    os.makedirs(os.path.join(FACES_DIR, 'unknown'), exist_ok=True)

    # Pre-populate unknown directory with synthetic noise (only need ~10 samples)
    unknown_dir = os.path.join(FACES_DIR, 'unknown')
    unknown_images = [f for f in os.listdir(unknown_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if len(unknown_images) < 10:
        print("Populating unknown class with synthetic background images...")
        for i in range(10 - len(unknown_images)):
            noise = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
            img = Image.fromarray(noise)
            img.save(os.path.join(unknown_dir, f'synthetic_unknown_{i}.jpg'))

    # List all subdirectories (representing registered students + unknown)
    classes = sorted([d for d in os.listdir(FACES_DIR) if os.path.isdir(os.path.join(FACES_DIR, d))])

    # Create class-to-index mapping
    class_to_idx = {cls_name: idx for idx, cls_name in enumerate(classes)}
    with open(CLASS_MAPPING_PATH, 'w') as f:
        json.dump(class_to_idx, f, indent=4)
    print(f"Constructed class mapping: {class_to_idx}")

    # --- Load existing feature cache ---
    # Cache keys are "classname/filename" -> feature vector
    cache = {}
    if os.path.exists(FEATURE_CACHE_PATH):
        try:
            loaded = np.load(FEATURE_CACHE_PATH, allow_pickle=True)
            cache = loaded['cache'].item()  # dict: key -> np.array(1280,)
            print(f"Loaded feature cache with {len(cache)} entries.")
        except Exception as e:
            print(f"Could not load feature cache, will rebuild: {e}")
            cache = {}

    features_list = []
    labels_list = []
    cache_updated = False
    base_model = get_base_model()

    for cls_name in classes:
        cls_dir = os.path.join(FACES_DIR, cls_name)
        cls_idx = class_to_idx[cls_name]

        for img_name in os.listdir(cls_dir):
            if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            cache_key = f"{cls_name}/{img_name}"

            if cache_key in cache:
                # Cache HIT: reuse pre-extracted feature vector instantly
                features_list.append(cache[cache_key])
                labels_list.append(cls_idx)
            else:
                # Cache MISS: extract via MobileNetV2 and store in cache
                img_path = os.path.join(cls_dir, img_name)
                try:
                    img = Image.open(img_path).convert('RGB')
                    img = img.resize((224, 224))
                    img_array = np.array(img, dtype=np.float32)
                    preprocessed = tf.keras.applications.mobilenet_v2.preprocess_input(
                        np.expand_dims(img_array, axis=0)
                    )
                    features = base_model(preprocessed, training=False).numpy()[0]
                    cache[cache_key] = features
                    cache_updated = True
                    features_list.append(features)
                    labels_list.append(cls_idx)
                except Exception as e:
                    print(f"Error processing image {img_path}: {e}")

    # Persist updated cache to disk
    if cache_updated:
        np.savez_compressed(FEATURE_CACHE_PATH, cache=cache)
        print(f"Feature cache updated and saved ({len(cache)} entries).")

    return np.array(features_list), np.array(labels_list), classes

class RetrainingCallback(tf.keras.callbacks.Callback):
    def __init__(self, progress_cb):
        super().__init__()
        self.progress_cb = progress_cb
        
    def on_epoch_begin(self, epoch, logs=None):
        if self.progress_cb:
            self.progress_cb(f"Epoch {epoch+1}/5 starting...")
            
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        loss = logs.get('loss', 0.0)
        acc = logs.get('accuracy', 0.0)
        if self.progress_cb:
            self.progress_cb(f"Epoch {epoch+1}/5: loss={loss:.4f}, accuracy={acc:.4f}")

def train_classifier(progress_callback=None):
    """
    Train a custom Keras classifier model on top of the pre-extracted features.
    """
    with model_lock:
        print("Starting classifier retraining...")
        if progress_callback:
            progress_callback("Loading dataset and extracting features...")
        X, y, classes = load_dataset()
        
        # We need at least 2 classes (unknown + 1 student)
        if len(classes) < 2:
            print("Insufficient classes to train classifier. Register at least one student.")
            if progress_callback:
                progress_callback("Failed: Register at least one student.")
            return False
            
        num_classes = len(classes)
        
        # Define a small MLP classifier
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(1280,)),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(num_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        # Setup callbacks
        callbacks = []
        if progress_callback:
            callbacks.append(RetrainingCallback(progress_callback))
            
        # Train model — 5 epochs is sufficient since MobileNetV2 features
        # are already highly discriminative; more epochs just waste time.
        model.fit(
            X, y,
            epochs=5,
            batch_size=16,
            shuffle=True,
            verbose=1,
            callbacks=callbacks
        )
        
        # Save model
        os.makedirs(os.path.dirname(CLASSIFIER_PATH), exist_ok=True)
        model.save(CLASSIFIER_PATH)
        print("Retraining completed. New Keras model saved.")
        if progress_callback:
            progress_callback("Retraining completed! Re-loading classifier...")
        
        # Reload models for inference
        reload_classifier_no_lock()
        return True

def load_classifier_for_inference():
    """Load the trained classifier and its mapping from disk."""
    global _classifier_model, _class_mapping, _inverse_class_mapping
    if _classifier_model is not None:
        return True
        
    if os.path.exists(CLASSIFIER_PATH) and os.path.exists(CLASS_MAPPING_PATH):
        try:
            print("Loading face classifier model for inference...")
            _classifier_model = tf.keras.models.load_model(CLASSIFIER_PATH)
            with open(CLASS_MAPPING_PATH, 'r') as f:
                _class_mapping = json.load(f)
            _inverse_class_mapping = {v: k for k, v in _class_mapping.items()}
            print("Face classifier loaded successfully.")
            return True
        except Exception as e:
            print(f"Error loading face classifier: {e}")
            return False
    else:
        print("Face classifier or class mapping file not found on disk.")
        return False

def reload_classifier_no_lock():
    """Reload classifier helper without locking (internal use)."""
    global _classifier_model, _class_mapping, _inverse_class_mapping
    _classifier_model = None
    _class_mapping = None
    _inverse_class_mapping = None
    return load_classifier_for_inference()

def reload_classifier():
    """Thread-safe reload of the classifier."""
    with model_lock:
        return reload_classifier_no_lock()

def predict_face(face_img, threshold=0.75):
    """
    Perform face classification.
    face_img: BGR numpy array of the face crop
    threshold: Probability confidence threshold to identify a student
    Returns: (label, confidence)
    """
    global _classifier_model, _inverse_class_mapping
    
    if _classifier_model is None:
        if not load_classifier_for_inference():
            return "Unknown", 0.0
            
    try:
        # Extract features
        features = extract_features(face_img)
        
        # Run inference in a lock to avoid concurrent session issues
        with model_lock:
            preds = _classifier_model(np.expand_dims(features, axis=0), training=False).numpy()[0]
            
        max_idx = np.argmax(preds)
        confidence = float(preds[max_idx])
        
        if confidence < threshold:
            return "Unknown", confidence
            
        label = _inverse_class_mapping.get(max_idx, "Unknown")
        
        # If classifier predicted 'unknown' class label, return "Unknown"
        if label == "unknown":
            return "Unknown", confidence
            
        return label, confidence
    except Exception as e:
        print(f"Prediction inference error: {e}")
        return "Unknown", 0.0
