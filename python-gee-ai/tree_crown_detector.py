"""
GeoESG — Tree Crown Detector (Classical Computer Vision)
========================================================
Deteksi tajuk pohon menggunakan metode Computer Vision klasik:
  HSV Color Thresholding → Morphological Filtering → Contour Detection

Metode ini mengikuti pendekatan yang di-review di:
  [1] Ke & Quackenbush (2011), "A review of methods for automatic individual
      tree-crown detection and delineation from passive remote sensing",
      Int. J. Remote Sensing, 32(17):4725-4747

Keterbatasan:
  - Bukan deep learning / neural network (bukan U-Net)
  - Input saat ini: citra RGB sintetis (simulasi resolusi 0.5m)
  - Untuk production: gunakan DeepForest (Weinstein et al., 2019, Methods
    in Ecology and Evolution) dengan citra satelit resolusi tinggi asli

Upgrade path ke deep learning:
  pip install deepforest  # Pre-trained Faster R-CNN (Weinstein et al., 2020)
"""

import os
import cv2
import numpy as np


class TreeCrownDetector:
    """
    Detektor tajuk pohon berbasis Computer Vision klasik.

    Metode: HSV thresholding + morphological opening + contour detection.
    Referensi: Ke & Quackenbush (2011), Int. J. Remote Sensing.

    Catatan: Ini BUKAN deep learning. Untuk akurasi lebih tinggi di
    lingkungan produksi, gunakan model pre-trained seperti DeepForest
    (Weinstein et al., 2019, Methods in Ecology and Evolution).
    """

    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "vision_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_synthetic_imagery(self, site_id, density=0.8):
        """
        Menghasilkan gambar RGB sintetis beresolusi tinggi (simulasi 0.5m/px).

        Catatan: Ini adalah simulasi untuk development. Untuk production,
        gunakan citra satelit resolusi tinggi asli (Airbus Pléiades,
        Planet SkySat, atau orthofoto drone).

        Args:
            site_id: Nama lokasi (digunakan sebagai random seed)
            density: Kerapatan vegetasi (0-1)

        Returns:
            str: Path ke citra sintetis yang dihasilkan
        """
        size = 1024  # 1024x1024 pixel (~500x500 meter pada resolusi 0.5m)

        # Background: tanah coklat/kuning
        img = np.zeros((size, size, 3), dtype=np.uint8)
        img[:] = (80, 140, 180)  # BGR

        # Spatial noise untuk realisme
        noise = np.random.randint(-20, 20, (size, size, 3))
        img = np.clip(img + noise, 0, 255).astype(np.uint8)

        # Generate tajuk pohon
        np.random.seed(hash(site_id) % 2**32)
        expected_trees = int(1200 * density)

        for _ in range(expected_trees):
            x = np.random.randint(10, size - 10)
            y = np.random.randint(10, size - 10)
            radius = np.random.randint(8, 25)

            color = (
                np.random.randint(20, 50),    # B
                np.random.randint(100, 180),  # G
                np.random.randint(20, 60),    # R
            )
            cv2.circle(img, (x, y), radius, color, -1)
            cv2.circle(img, (x + 2, y + 2), radius, (20, 40, 20), 2)

        img_path = os.path.join(self.output_dir, f"{site_id}_synthetic_0_5m.png")
        cv2.imwrite(img_path, img)
        return img_path

    def detect_tree_crowns(self, image_path, site_id):
        """
        Deteksi tajuk pohon menggunakan Classical Computer Vision.

        Pipeline:
          1. Konversi BGR → HSV color space
          2. Masking warna hijau (chlorophyll range)
          3. Morphological opening (noise removal + crown separation)
          4. Contour detection (instance identification)
          5. Area filtering (min 50px² untuk menghilangkan noise)

        Metode ini mengikuti review di Ke & Quackenbush (2011).

        Args:
            image_path: Path ke citra input (RGB)
            site_id: Nama lokasi

        Returns:
            tuple: (tree_count, result_image_path)
        """
        img = cv2.imread(image_path)
        if img is None:
            return 0, None

        # 1. Color space transformation
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 2. Green vegetation mask (chlorophyll spectral range)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # 3. Morphological opening (separate touching crowns)
        kernel = np.ones((5, 5), np.uint8)
        mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

        # 4. Contour detection (instance segmentation)
        contours, _ = cv2.findContours(
            mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 5. Filter by minimum crown area (50px² ≈ 12.5m² at 0.5m resolution)
        valid_trees = [cnt for cnt in contours if cv2.contourArea(cnt) > 50]
        tree_count = len(valid_trees)

        # Visualize detections
        output_img = img.copy()
        cv2.drawContours(output_img, valid_trees, -1, (0, 0, 255), 2)
        cv2.putText(
            output_img,
            f"CV Detection: {tree_count} Trees (Classical Method)",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
        )

        out_path = os.path.join(
            self.output_dir, f"{site_id}_cv_segmentation.png"
        )
        cv2.imwrite(out_path, output_img)

        return tree_count, out_path


# ── Backward Compatibility ───────────────────────────────────────
# Alias untuk kode lama yang masih menggunakan nama lama
TreeVisionUNet = TreeCrownDetector


# ── Standalone Testing ───────────────────────────────────────────
if __name__ == "__main__":
    detector = TreeCrownDetector()
    site = "Lombok_CV_Test"

    print(f"📡 Generating synthetic 0.5m imagery for {site}...")
    img_path = detector.generate_synthetic_imagery(site, density=0.85)

    print("🔍 Running Classical CV tree crown detection...")
    print("   Method: HSV Threshold → Morphological Open → Contour Detection")
    print("   Ref: Ke & Quackenbush (2011), Int. J. Remote Sensing")
    count, result_img = detector.detect_tree_crowns(img_path, site)

    print(f"✅ Detected {count} individual tree crowns.")
    print(f"🖼️ Segmentation result: {result_img}")
    print("\n⚠️  Note: For production, upgrade to DeepForest")
    print("   (Weinstein et al., 2019, Methods in Ecology and Evolution)")
