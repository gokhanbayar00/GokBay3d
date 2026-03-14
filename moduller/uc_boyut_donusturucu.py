"""
Üç Boyut Dönüştürücü Modülü

Bu modül, derinlik haritasından veya parametrik şekillerden
STL/PLY/GLB gibi 3B model dosyaları üreten araçlar sağlar.
"""

import base64
from typing import Tuple

import numpy as np
import trimesh


def derinlikten_mesh_olustur(derinlik: np.ndarray) -> trimesh.Trimesh:
    """Derinlik haritasından bir üçgen ağ (mesh) oluşturur.

    Args:
        derinlik: 2B numpy dizisi (0-255) derinlik haritası.

    Returns:
        Trimesh nesnesi.
    """

    # Derinlik haritası boyutlarını al
    h, w = derinlik.shape

    # Her piksel için x,y koordinatları üret
    x = np.arange(w, dtype=np.float32)
    y = np.arange(h, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    # Derinlik değerlerini z eksenine yerleştir
    # 0-255 aralığını 0-1 aralığına ölçekliyoruz
    zz = derinlik.astype(np.float32) / 255.0

    # Nokta bulutu (vertex listesi) oluştur
    # Her piksel bir vertex
    vertices = np.column_stack((xx.ravel(), yy.ravel(), zz.ravel()))

    # Yüzey (faces) oluşturmak için iki üçgen kullanacağız
    faces = []
    for yi in range(h - 1):
        for xi in range(w - 1):
            # Dört köşe vertex indeksi
            v0 = yi * w + xi
            v1 = yi * w + (xi + 1)
            v2 = (yi + 1) * w + xi
            v3 = (yi + 1) * w + (xi + 1)

            # İki üçgen oluştur
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces, dtype=np.int64)

    # Trimesh kullanarak mesh oluştur
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    return mesh


def derinlikten_stl_olustur(derinlik: np.ndarray, hedef_dosya: str, olcek: float = 1.0) -> None:
    """Derinlik haritasından STL dosyası üretir.

    Args:
        derinlik: 2B numpy dizisi (0-255) derinlik haritası.
        hedef_dosya: Kaydedilecek dosyanın yolu.
        olcek: Modelin ölçeği.
    """

    mesh = derinlikten_mesh_olustur(derinlik)
    mesh.apply_scale(olcek)
    mesh.export(hedef_dosya)


def parametrik_mesh_olustur(sekil: str, olcek: float = 1.0) -> trimesh.Trimesh:
    """Anahtar kelimeye göre basit parametrik bir 3B model üretir.

    Args:
        sekil: Oluşturulacak şeklin adı (ör. "küp", "kure").
        olcek: Modelin ölçeği.

    Returns:
        Trimesh nesnesi.
    """

    sekil = sekil.strip().lower()
    mesh = None

    if sekil in ["küp", "kutu", "kare"]:
        # Küp/box: 1 birim kenar uzunluğu
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    elif sekil in ["kure", "top", "sphere"]:
        mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
    elif sekil in ["silindir", "cylinder"]:
        mesh = trimesh.creation.cylinder(radius=0.4, height=1.0, sections=32)
    elif sekil in ["koni", "cone"]:
        mesh = trimesh.creation.cone(radius=0.4, height=1.0, sections=32)
    elif sekil in ["düzlem", "plane", "taban"]:
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 0.02))
    elif sekil in ["torus", "halka"]:
        mesh = trimesh.creation.torus(radius=0.6, tube_radius=0.2)
    else:
        # Bilinmeyen anahtar kelime için bir küp üret
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))

    mesh.apply_scale(olcek)
    return mesh


def metinden_sahne_olustur(metin: str, olcek: float = 1.0) -> trimesh.Scene:
    """Basit bir dil modeli benzeri yorumla metinden 3B sahne oluşturur.

    Bu fonksiyon, metindeki anahtar kelimelere göre bir masa, küre,
    silindir gibi objeler oluşturur ve basit bir sahne haline getirir.

    Args:
        metin: Sahneyi tanımlayan Türkçe metin.
        olcek: Sahnedeki tüm öğelerin ölçeği.

    Returns:
        Trimesh Scene nesnesi.
    """

    metin_low = metin.lower()

    # Sahne nesnesi oluştur
    scene = trimesh.Scene()

    # Zemin düzlemi ekle
    zem = trimesh.creation.box(extents=(3.0, 3.0, 0.02))
    zem.apply_translation((0, 0, -0.01))
    zem.visual.material = _pbr_material((180, 180, 180), metallic=0.0, roughness=1.0)
    scene.add_geometry(zem, node_name="zemin")

    # Masa varsa sahneye ekle
    if "masa" in metin_low or "table" in metin_low:
        masa = trimesh.creation.box(extents=(1.5, 0.8, 0.1))
        masa.apply_translation((0, 0, 0.05))
        masa.visual.material = _pbr_material((120, 80, 50), metallic=0.1, roughness=0.7)
        scene.add_geometry(masa, node_name="masa")

        # Masa üzerinde bir obje varsa
        if "üzerinde" in metin_low or "üstünde" in metin_low or "üzerine" in metin_low:
            if "kure" in metin_low or "küre" in metin_low or "top" in metin_low:
                obje = trimesh.creation.icosphere(subdivisions=3, radius=0.2)
                obje.apply_translation((0, 0, 0.3))
                obje.visual.material = _pbr_material((200, 50, 50), metallic=0.2, roughness=0.4)
                scene.add_geometry(obje, node_name="ust_kure")
            elif "silindir" in metin_low:
                obje = trimesh.creation.cylinder(radius=0.15, height=0.4, sections=32)
                obje.apply_translation((0, 0, 0.2))
                obje.visual.material = _pbr_material((50, 150, 200), metallic=0.1, roughness=0.6)
                scene.add_geometry(obje, node_name="ust_silindir")
            elif "koni" in metin_low:
                obje = trimesh.creation.cone(radius=0.15, height=0.4, sections=32)
                obje.apply_translation((0, 0, 0.2))
                obje.visual.material = _pbr_material((50, 200, 100), metallic=0.0, roughness=0.5)
                scene.add_geometry(obje, node_name="ust_koni")

    # Eğer sadece bir şekil istenmişse, sahneye merkezde ekle
    if not scene.geometry or len(scene.geometry) == 1:
        # Daha önce masa eklenmemişse ya da sadece zemin varsa
        if "kure" in metin_low or "küre" in metin_low or "top" in metin_low:
            obje = trimesh.creation.icosphere(subdivisions=3, radius=0.4)
            obje.apply_translation((0, 0, 0.4))
            obje.visual.material = _pbr_material((200, 50, 50), metallic=0.2, roughness=0.4)
            scene.add_geometry(obje, node_name="kure")
        elif "silindir" in metin_low:
            obje = trimesh.creation.cylinder(radius=0.2, height=0.7, sections=32)
            obje.apply_translation((0, 0, 0.35))
            obje.visual.material = _pbr_material((50, 150, 200), metallic=0.1, roughness=0.6)
            scene.add_geometry(obje, node_name="silindir")
        elif "koni" in metin_low:
            obje = trimesh.creation.cone(radius=0.2, height=0.7, sections=32)
            obje.apply_translation((0, 0, 0.35))
            obje.visual.material = _pbr_material((50, 200, 100), metallic=0.0, roughness=0.5)
            scene.add_geometry(obje, node_name="koni")
        elif "küp" in metin_low or "kutu" in metin_low or "kare" in metin_low:
            obje = trimesh.creation.box(extents=(0.7, 0.7, 0.7))
            obje.apply_translation((0, 0, 0.35))
            obje.visual.material = _pbr_material((150, 150, 200), metallic=0.1, roughness=0.5)
            scene.add_geometry(obje, node_name="kutu")

    # Sahneyi ölçeklendir
    if olcek != 1.0:
        scene.apply_scale(olcek)

    return scene


def scene_to_glb_data_uri(scene: trimesh.Scene) -> str:
    """Trimesh Scene'i GLB veri URI'sine çevirir.

    GLB veri URI'si, HTML içinde üç.js kullanarak önizleme için kullanılabilir.

    Returns:
        data URI string.
    """

    glb_bytes = scene.export(file_type="glb")
    b64 = base64.b64encode(glb_bytes).decode("ascii")
    return f"data:model/gltf-binary;base64,{b64}"


def _pbr_material(base_color: Tuple[int, int, int], metallic: float = 0.0, roughness: float = 0.8):
    """Basit bir PBR materyal oluşturur.

    Args:
        base_color: RGB renk (0-255 arası).
        metallic: Metalik değer (0.0 - 1.0).
        roughness: Pürüzlülük değeri (0.0 - 1.0).

    Returns:
        trimesh.visual.material.PBRMaterial
    """

    # Üç.js GLTF'de kullanılan renk 0-1 aralığında
    base_color_norm = [c / 255.0 for c in base_color] + [1.0]
    material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=base_color_norm,
        metallicFactor=float(metallic),
        roughnessFactor=float(roughness),
    )
    return material


def mesh_renkli_kaydet(
    mesh: trimesh.Trimesh,
    hedef_dosya: str,
    dosya_tipi: str = "ply",
    renk: Tuple[int, int, int] = (200, 150, 100),
    metalik: float = 0.0,
    pürüzlülük: float = 0.8,
) -> None:
    """Mesh'i renkli olarak kaydeder.

    STL formatı kendisi renk bilgisi desteklemez, bu nedenle renklendirme
    için PLY veya GLB formatları tercih edilir.

    Args:
        mesh: Kaydedilecek mesh.
        hedef_dosya: Dosya yolu (uzantı modeline göre değişir).
        dosya_tipi: "stl", "ply" veya "glb".
        renk: RGB renk değeri (0-255 aralığında).
        metalik: Metaliklik (0-1 arası).
        pürüzlülük: Roughness (0-1 arası).
    """

    dosya_tipi = dosya_tipi.lower()

    if dosya_tipi in ["ply", "glb"]:
        # Trimesh PBR materyali kullanarak renk ve materyal bilgisi ekle
        mesh.visual.material = _pbr_material(renk, metalik, pürüzlülük)

    mesh.export(hedef_dosya, file_type=dosya_tipi)


def mesh_to_glb_data_uri(mesh: trimesh.Trimesh) -> str:
    """Mesh'i GLB formatında veri URI'sine çevirir.

    Bu URI, HTML içinde üç.js kullanarak önizleme için kullanılabilir.

    Returns:
        data URI string.
    """

    glb_bytes = mesh.export(file_type="glb")
    b64 = base64.b64encode(glb_bytes).decode("ascii")
    return f"data:model/gltf-binary;base64,{b64}"
