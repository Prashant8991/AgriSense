import os
import tensorflow as tf
import numpy as np
import json
import cv2
from PIL import Image

class DiseaseClassifier:
    def __init__(self, model_path, classes_path=None):
        self.model_path = model_path
        self.classes_path = classes_path
        self._model = None
        self._class_names = []
        self._last_conv_layer_name = None

    def load(self):
        if self._model is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
            
            self._model = tf.keras.models.load_model(self.model_path)
            
            # Ensure model is built for functional-like layer access
            try:
                self._model.build((None, 224, 224, 3))
            except:
                pass

            # Automatically find the last convolutional layer
            for layer in reversed(self._model.layers):
                if isinstance(layer, (tf.keras.layers.Conv2D, tf.keras.layers.SeparableConv2D)):
                    self._last_conv_layer_name = layer.name
                    break
            
            if not self._last_conv_layer_name:
                # Fallback for nested models (like ResNet/MobileNet-based Transfer Learning)
                for layer in reversed(self._model.layers):
                    if hasattr(layer, 'layers'): # is a functional model or sequential inside
                         for sublayer in reversed(layer.layers):
                             if isinstance(sublayer, (tf.keras.layers.Conv2D, tf.keras.layers.SeparableConv2D)):
                                 self._last_conv_layer_name = sublayer.name
                                 break
                    if self._last_conv_layer_name: break

            if self.classes_path and os.path.exists(self.classes_path):
                with open(self.classes_path, "r") as f:
                    self._class_names = json.load(f)
        return self._model, self._class_names

    def get_grad_models(self):
        """Creates a grad-cam compatible sub-model."""
        model, _ = self.load()
        if not self._last_conv_layer_name:
            return None
        
        if not hasattr(self, '_grad_model') or self._grad_model is None:
            # We create a new functional model that clones the layers
            # to avoid referencing the Sequential model's .output which can be buggy
            try:
                # Try functional approach first
                self._grad_model = tf.keras.models.Model(
                    [model.inputs], [model.get_layer(self._last_conv_layer_name).output, model.output]
                )
            except Exception as e:
                # Fallback for Sequential models: Reconstruct a functional model
                inputs = tf.keras.Input(shape=(224, 224, 3))
                x = inputs
                conv_out = None
                for layer in model.layers:
                    x = layer(x)
                    if layer.name == self._last_conv_layer_name:
                        conv_out = x
                self._grad_model = tf.keras.models.Model(inputs, [conv_out, x])
        
        return self._grad_model

    def predict(self, image_path, generate_heatmap=False):
        model, class_names = self.load()
        
        # Load and preprocess image
        img = Image.open(image_path).convert("RGB").resize((224, 224))
        img_array = np.array(img) / 255.0
        img_input = np.expand_dims(img_array, axis=0)

        preds = model.predict(img_input, verbose=0)
        idx = int(np.argmax(preds))
        
        disease = class_names[idx] if class_names else f"Class_{idx}"
        confidence = round(float(preds[0][idx]) * 100, 2)
        
        heatmap_path = None
        if generate_heatmap:
            try:
                heatmap_path = self.generate_gradcam(image_path, idx, disease, confidence)
            except Exception as e:
                print(f"Heatmap generation failed: {e}")
            
        return disease, confidence, heatmap_path

    def generate_gradcam(self, image_path, class_idx, disease_name="", confidence=0, intensity=0.3, res=224):
        """Generates localization overlay with red circles around diseased spots."""
        grad_model = self.get_grad_models()
        if not grad_model:
             return None

        # 1. Load image and predict activations
        img = cv2.imread(image_path)
        if img is None: return None
        
        orig_h, orig_w = img.shape[:2]
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (res, res))
        img_input = np.expand_dims(img_resized / 255.0, axis=0)

        with tf.GradientTape() as tape:
            conv_outputs, predictions = grad_model(img_input)
            loss = predictions[:, class_idx]

        output = conv_outputs[0]
        grads = tape.gradient(loss, conv_outputs)[0]

        gate_f = tf.reduce_mean(grads, axis=(0, 1))
        cam = output @ gate_f[..., tf.newaxis]
        cam = tf.squeeze(cam)

        m_val = tf.math.reduce_max(cam)
        heatmap = tf.maximum(cam, 0) / (m_val if m_val > 0 else 1.0)
        heatmap = heatmap.numpy()

        # 2. Convert to mask and detect spots
        heatmap_resized = cv2.resize(heatmap, (orig_w, orig_h))
        heatmap_uint8 = np.uint8(255 * heatmap_resized)
        
        # Lower threshold (120 instead of 155) to catch more diseased regions
        _, mask = cv2.threshold(heatmap_uint8, 120, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to group spots
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=1)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 3. Create visualization
        heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        superimposed_img = cv2.addWeighted(heatmap_color, 0.25, img, 0.75, 0)
        
        spot_count = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Area > 80 pixels is enough for a spot
            if area > 80:
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                cv2.circle(superimposed_img, (int(x), int(y)), int(radius), (0, 0, 255), 4) # Red Circle (BGR)
                cv2.circle(superimposed_img, (int(x), int(y)), 2, (0, 0, 255), -1)
                spot_count += 1

        # 4. Add Professional Diagnosis Badge
        label_text = f"LOCALIZATION: {disease_name.upper()} ({confidence}%)"
        font = cv2.FONT_HERSHEY_DUPLEX
        fs = max(0.6, orig_w / 900.0) 
        thickness = 2
        (tw, th), _ = cv2.getTextSize(label_text, font, fs, thickness)
        
        overlay = superimposed_img.copy()
        cv2.rectangle(overlay, (0, 0), (orig_w, th + 40), (0, 0, 255), -1) # Red accent bar
        cv2.addWeighted(overlay, 0.4, superimposed_img, 0.6, 0, superimposed_img)
        cv2.putText(superimposed_img, label_text, (20, th + 20), font, fs, (255, 255, 255), thickness)

        # 5. Save the result
        # Ensure path is cross-platform and forward-slash based for URL return
        output_dir = "static/uploads/heatmaps"
        os.makedirs(output_dir, exist_ok=True)
        filename = "heatmap_" + os.path.basename(image_path)
        output_path = os.path.join(output_dir, filename)
        cv2.imwrite(output_path, superimposed_img)
        
        # Return path with forward slashes for the browser
        return output_path.replace("\\", "/")

    def live_gradcam(self, frame, class_idx, disease_name="", confidence=0, intensity=0.3, res=224):
        """Generates real-time localization and circles for webcam feed."""
        grad_model = self.get_grad_models()
        if not grad_model:
             return frame

        h, w = frame.shape[:2]
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (res, res))
        img_input = np.expand_dims(img_resized / 255.0, axis=0)

        with tf.GradientTape() as tape:
            conv_outputs, predictions = grad_model(img_input)
            loss = predictions[:, class_idx]

        output = conv_outputs[0]
        grads = tape.gradient(loss, conv_outputs)[0]

        gate_f = tf.reduce_mean(grads, axis=(0, 1))
        cam = output @ gate_f[..., tf.newaxis]
        cam = tf.squeeze(cam)

        m_val = tf.math.reduce_max(cam)
        heatmap = tf.maximum(cam, 0) / (m_val if m_val > 0 else 1.0)
        heatmap = heatmap.numpy()

        heatmap_resized = cv2.resize(heatmap, (w, h))
        heatmap_uint8 = np.uint8(255 * heatmap_resized)

        # Detect Spots
        _, mask = cv2.threshold(heatmap_uint8, 160, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=1)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Visualization
        heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
        superimposed_img = cv2.addWeighted(heatmap_color, 0.2, frame, 0.8, 0)
        
        for cnt in contours:
            if cv2.contourArea(cnt) > 120:
                (x, y), radius = cv2.minEnclosingCircle(cnt)
                cv2.circle(superimposed_img, (int(x), int(y)), int(radius), (0, 0, 255), 3)

        # Label Banner
        label = f"LIVE: {disease_name.upper()} ({confidence}%)"
        cv2.rectangle(superimposed_img, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.putText(superimposed_img, label, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return np.uint8(np.clip(superimposed_img, 0, 255))
