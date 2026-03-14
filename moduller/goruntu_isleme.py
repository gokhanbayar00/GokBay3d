"""
Görüntü İşleme Modülü

Bu modül, metin ve resim girdilerini alarak derinlik haritası üretir.
Derinlik haritası, 0-255 arasında değerler içeren bir gri tonlama görüntüsüdür.
"""

import os
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

# MiDaS derinlik tahmini için model URL'si
_MIDAS_MODEL_URL = (
    "https://github.com/isl-org/MiDaS/releases/download/v3_1/midas_v21_small.onnx"
)

# Model dosyası workspace içinde saklanır
_MIDAS_MODEL_PATH = Path(__file__).parent / "models" / "midas_v21_small.onnx"


def _midas_model_indir(model_path: Path) -> None:
    """MiDaS modelini indirebilirsek indirir."""

    try:
        import requests

        model_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(_MIDAS_MODEL_URL, stream=True, timeout=30)
        resp.raise_for_status()

        with open(model_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception:
        # Bağlantı yoksa ya da hata varsa, model indirilemeyecek
        pass


def metinden_derinlik_haritası_olustur(metin: str) -> np.ndarray:
    """Metin girdisinden basit bir derinlik haritası oluşturur.

    Bu fonksiyon, girilen metnin uzunluğunu ve karakter bilgisini kullanarak
    bir matriste derinlik değerleri hesaplar.

    Args:
        metin: Derinlik haritasını oluşturmak için kullanılacak metin.

    Returns:
        8 bitlik (0-255) numpy dizisi olarak derinlik haritası.
    """

    # Derinlik haritası için sabit boyut
    yukseklik = 160
    genislik = 160

    # Metnin her karakterinin kodunu al ve normalize et
    # Bu, metinler arasında farklı yüksek/pikseller oluşturur.
    kodlar = [ord(k) for k in metin[:genislik]]
    if not kodlar:
        kodlar = [0]

    # Kodları 0-255 aralığına sığdır
    kod_matris = np.array(kodlar, dtype=np.float32)
    kod_matris = (kod_matris - kod_matris.min()) / max(1, kod_matris.ptp())
    kod_matris = (kod_matris * 255).astype(np.uint8)

    # Sabit bir desen üretmek için tekrarlayıp matris oluştur
    derinlik = np.tile(kod_matris, (yukseklik, 1))

    # Metin uzunluğu derinliği etkiler (daha uzun -> daha yüksek noktalar)
    uzunluk_etkisi = min(len(metin), 255)
    derinlik = np.clip(derinlik + uzunluk_etkisi, 0, 255).astype(np.uint8)

    return derinlik


def resimden_derinlik_haritası_olustur(dosya) -> np.ndarray:
    """Yüklenen bir resmi alıp basit bir derinlik haritasına dönüştürür.

    Bu fonksiyon, resmi gri tonlamaya çevirir ve pikselleri 0-255 aralığında
    bir numpy dizisi olarak geri döndürür.

    Args:
        dosya: Streamlit veya benzeri bir dosya yükleyicisinden gelen Dosya nesnesi.

    Returns:
        8 bitlik (0-255) numpy dizisi olarak derinlik haritası.
    """

    # Dosyayı PIL kullanarak aç
    # Streamlit, dosya nesnesini bir BytesIO gibi verir
    resim = Image.open(BytesIO(dosya.read()))

    # Gri tonlamaya çevir
    gri_resim = resim.convert("L")

    # Boyutu normalize et (ciddi uzunluklardan kaçınmak için)
    maks_boyut = 256
    gri_resim.thumbnail((maks_boyut, maks_boyut), Image.ANTIALIAS)

    # NumPy dizisine dönüştür
    derinlik = np.array(gri_resim, dtype=np.uint8)

    return derinlik


def resimden_derinlik_haritası_midas(dosya) -> np.ndarray:
    """Resimden MiDaS derinlik tahmini kullanarak derinlik haritası üretir.

    MiDaS modeli, resimdeki her piksel için bir derinlik değeri tahmin eder.
    Bu fonksiyon, resmi model girişine hazırlayıp tahmin çıktısını 0-255 aralığına
    ölçekler.

    Args:
        dosya: Streamlit veya benzeri bir dosya yükleyicisinden gelen Dosya nesnesi.

    Returns:
        8 bitlik (0-255) numpy dizisi olarak derinlik haritası.
    """

    try:
        import cv2
    except ImportError as e:
        raise ImportError(
            "OpenCV (cv2) yüklü değil. `pip install opencv-python` ile kurun."
        ) from e

    # Model dosyasını hazırla
    if not _MIDAS_MODEL_PATH.exists():
        _midas_model_indir(_MIDAS_MODEL_PATH)

    if not _MIDAS_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"MiDaS modeli bulunamadı: {_MIDAS_MODEL_PATH}. İnternet bağlantısı varsa tekrar deneyin."
        )

    # Modeli yükle
    net = cv2.dnn.readNet(str(_MIDAS_MODEL_PATH))

    # Resmi aç ve BGR formata çevir
    img = Image.open(BytesIO(dosya.read())).convert("RGB")
    img = np.array(img)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # MiDaS için standart boyut (hız için küçük model kullanıyoruz)
    input_size = 256
    img_resized = cv2.resize(img, (input_size, input_size), interpolation=cv2.INTER_AREA)
    blob = cv2.dnn.blobFromImage(
        img_resized,
        scalefactor=1.0 / 255.0,
        size=(input_size, input_size),
        mean=(0.485, 0.456, 0.406),
        swapRB=True,
        crop=False,
    )

    net.setInput(blob)
    derinlik = net.forward()[0, 0]

    # Model çıktısını orijinal boyuta yeniden boyutlandır
    derinlik = cv2.resize(derinlik, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC)

    # 0-255 aralığına ölçekle
    min_val, max_val = derinlik.min(), derinlik.max()
    derinlik_norm = (derinlik - min_val) / max(1e-6, (max_val - min_val))
    derinlik_255 = (derinlik_norm * 255).astype(np.uint8)

    return derinlik_255
