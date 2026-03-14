# GökBay3D

Bu proje, metin veya resim girdisinden basit bir **STL** 3B model oluşturan bir **Streamlit** uygulamasıdır.

## Çalıştırma

1. Sanal ortam oluşturun ve aktif edin.
2. Gerekli paketleri yükleyin:

```bash
pip install streamlit trimesh numpy pillow opencv-python requests
```

3. Uygulamayı çalıştırın:

```bash
streamlit run ana_uygulama.py
```

> **Not:** MiDaS derinlik tahmini için ilk çalıştırmada model dosyası internetten indirilecektir. İndirme başarısız olursa, uygulama basit gri tonlama derinliği üretir.

## Klasör Yapısı

- `ana_uygulama.py`: Uygulamanın giriş noktası.
- `moduller/`: Görüntü işleme ve 3B dönüştürme modülleri.
- `cikti_modelleri/`: Oluşturulan STL dosyalarının kaydedildiği yer.
- `arayuz_ayarlari/`: Arayüz için ek ayarların saklanabileceği klasör.
