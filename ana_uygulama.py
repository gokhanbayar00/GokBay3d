"""
GökBay3D - Ana uygulama

Bu dosya, Streamlit tabanlı bir web arayüzü sağlar.
Kullanıcıdan metin veya resim girdisi alır, derinlik tahmini üretir ve
modeli **STL/PLY/GLB** formatına çevirir.
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from pathlib import Path

from moduller.goruntu_isleme import (
    metinden_derinlik_haritası_olustur,
    resimden_derinlik_haritası_olustur,
    resimden_derinlik_haritası_midas,
)
from moduller.uc_boyut_donusturucu import (
    derinlikten_mesh_olustur,
    derinlikten_stl_olustur,
    mesh_renkli_kaydet,
    mesh_to_glb_data_uri,
    metinden_sahne_olustur,
    scene_to_glb_data_uri,
    parametrik_mesh_olustur,
)

# Uygulamanın çalıştığı dizin
proje_kok_dizini = Path(__file__).parent
# Üretilen dosyaların kaydedileceği dizin
cikti_dizini = proje_kok_dizini / "cikti_modelleri"
# Eğer çıktı dizini yoksa oluşturulur
cikti_dizini.mkdir(exist_ok=True)

# Streamlit sayfa başlığı
st.set_page_config(page_title="GökBay3D - 3B Model Üretici", layout="wide")
st.title("GökBay3D - 3D Model Üretici")

st.markdown(
    """
    Bu araç, bir **metin** veya **resim** girdisinden derinlik haritası tahmini yapar
    ve bunu **STL / PLY / GLB** formatına çevirir. Ayrıca parametrik şekiller üretebilirsiniz.
    """
)

# Kullanıcıdan giriş tipi seçimi alınır
girdi_tipi = st.radio("Girdi türünü seçin:", ("Metin", "Resim"))

# Model / sahne / derinlik için kullanılacak temel değişkenler
derinlik_haritası = None
model_mesh = None
model_sahne = None


def _hex_to_rgb(hexc: str):
    """Hex renk kodunu (ör. #FF8800) RGB üçlüsüne çevirir."""

    hexc = hexc.lstrip("#")
    return tuple(int(hexc[i : i + 2], 16) for i in (0, 2, 4))


def _onizleme_html(
    glb_data_uri: str,
    yukseklik: int = 400,
    wireframe: bool = False,
    show_ground: bool = True,
    ambient_intensity: float = 0.8,
    directional_intensity: float = 1.0,
) -> str:
    """Three.js kullanarak GLB modelini gömülü olarak önizleme HTML'i hazırlar."""

    html = """
    <div id=\"gokbay3d_viewer\" style=\"width:100%;height:{yukseklik}px;\"></div>
    <script type=\"module\">
      import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.module.js';
      import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.158.0/examples/jsm/controls/OrbitControls.js';
      import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.158.0/examples/jsm/loaders/GLTFLoader.js';

      const container = document.getElementById('gokbay3d_viewer');
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf0f0f0);
      const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
      camera.position.set(0, -2, 1.5);

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(container.clientWidth, container.clientHeight);
      container.appendChild(renderer.domElement);

      const ambientLight = new THREE.HemisphereLight(0xffffff, 0x444444, {ambient});
      scene.add(ambientLight);
      const dirLight = new THREE.DirectionalLight(0xffffff, {directional});
      dirLight.position.set(0, 0, 1);
      scene.add(dirLight);

      if ({show_ground}) {
        const ground = new THREE.Mesh(
          new THREE.PlaneGeometry(10, 10),
          new THREE.MeshStandardMaterial({ color: 0xdddddd, roughness: 1.0, metalness: 0 })
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -0.01;
        ground.receiveShadow = true;
        scene.add(ground);
      }

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(0, 0, 0);
      controls.update();

      const loader = new GLTFLoader();
      loader.load(
        '{glb_data_uri}',
        (gltf) => {
          const model = gltf.scene;
          scene.add(model);
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              if ({wireframe}) {
                child.material.wireframe = true;
              }
            }
          });
          const box = new THREE.Box3().setFromObject(model);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());
          model.position.sub(center);
          camera.position.set(size.x * 1.2, size.y * 1.2, size.z * 1.5);
          camera.lookAt(0, 0, 0);
        },
        undefined,
        (error) => console.error(error)
      );

      function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      }

      animate();
    </script>
    """

    return (
        html
        .replace("{glb_data_uri}", glb_data_uri)
        .replace("{yukseklik}", str(yukseklik))
        .replace("{wireframe}", "true" if wireframe else "false")
        .replace("{show_ground}", "true" if show_ground else "false")
        .replace("{ambient}", str(ambient_intensity))
        .replace("{directional}", str(directional_intensity))
    )


if girdi_tipi == "Metin":
    # Metin girdisi için birkaç farklı işlem modu sunuluyor
    metin_modu = st.selectbox(
        "Metin işleme modu:",
        ("Derinlik Haritası", "Parametrik Şekil", "Parametrik Sahne"),
    )

    kullanici_metni = st.text_area("Model için açıklama metni girin:", height=150)

    if kullanici_metni:
        if metin_modu == "Derinlik Haritası":
            # Metni derinlik haritasına çevir
            derinlik_haritası = metinden_derinlik_haritası_olustur(kullanici_metni)
            st.success("Derinlik haritası oluşturuldu.")
            st.image(derinlik_haritası, caption="Oluşturulan derinlik haritası", use_column_width=True)

            # Derinlik haritasından mesh oluşturup önizleme
            model_mesh = derinlikten_mesh_olustur(derinlik_haritası)
            model_sahne = None

        elif metin_modu == "Parametrik Şekil":
            # Parametrik tek bir şekil oluşturma
            sekil = st.selectbox(
                "Parametrik şekil seçin:",
                ("Küp", "Küre", "Silindir", "Koni", "Torus", "Düzlem"),
            )
            renk = st.color_picker("Model rengi (PLY/GLB için)", "#ff8800")

            model_mesh = parametrik_mesh_olustur(sekil, 1.0)
            model_sahne = None

            # 3B önizleme (GLB veri URI'si üzerinden)
            glb_uri = mesh_to_glb_data_uri(model_mesh)
            components.html(_onizleme_html(glb_uri), height=450)

        else:
            # Metin ile parametrik sahne betimleme
            st.info("Metin, örn. 'masanın üzerinde bir küre' şeklinde sahne betimlemesi yapabilir.")
            olcek = st.slider("Sahne ölçeği", min_value=0.2, max_value=5.0, value=1.0, step=0.1)

            model_sahne = metinden_sahne_olustur(kullanici_metni, olcek=olcek)
            model_mesh = None
            glb_uri = scene_to_glb_data_uri(model_sahne)
            components.html(_onizleme_html(glb_uri), height=450)

elif girdi_tipi == "Resim":
    # Resim üzerinden derinlik tahmini yapılırken iki yöntem sunuyoruz
    resim_yontemi = st.selectbox(
        "Derinlik tahmini yöntemi:",
        ("Basit Gri Ton", "MiDaS Derinlik Tahmini"),
    )
    yuklenen_dosya = st.file_uploader("Bir resim yükleyin (PNG/JPG)", type=["png", "jpg", "jpeg"])

    if yuklenen_dosya is not None:
        if resim_yontemi == "MiDaS Derinlik Tahmini":
            try:
                derinlik_haritası = resimden_derinlik_haritası_midas(yuklenen_dosya)
                st.success("MiDaS derinlik tahmini oluşturuldu.")
            except Exception as exc:
                st.error(str(exc))
                derinlik_haritası = None
        else:
            derinlik_haritası = resimden_derinlik_haritası_olustur(yuklenen_dosya)
            st.success("Basit derinlik haritası oluşturuldu.")

        if derinlik_haritası is not None:
            st.image(derinlik_haritası, caption="Oluşturulan derinlik haritası", use_column_width=True)
            model_mesh = derinlikten_mesh_olustur(derinlik_haritası)

# Eğer mesh veya sahne mevcutsa kullanıcıya indirme seçenekleri sun
if model_mesh is not None or model_sahne is not None:
    st.markdown("---")
    st.subheader("Model İndirme ve Ayarlar")

    # Önizleme kontrolleri
    st.markdown("**Önizleme ayarları**")
    wireframe = st.checkbox("Wireframe modu", value=False)
    show_ground = st.checkbox("Zemin göster", value=True)
    ambient_intensity = st.slider("Ortam ışığı yoğunluğu", min_value=0.0, max_value=2.0, value=0.8, step=0.1)
    directional_intensity = st.slider("Yönlendirilmiş ışık yoğunluğu", min_value=0.0, max_value=2.0, value=1.0, step=0.1)

    # Ölçek ve materyal ayarları
    st.markdown("**Materyal ve ölçek**")
    olcek = st.slider("Modeli ölçeklendir (1 = orijinal)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    renk = st.color_picker("Genel model rengi (PLY/GLB)", "#ff8800")
    metalik = st.slider("Metaliklik", min_value=0.0, max_value=1.0, value=0.1, step=0.1)
    pürüzlülük = st.slider("Pürüzlülük (roughness)", min_value=0.0, max_value=1.0, value=0.6, step=0.05)
    renk_rgb = _hex_to_rgb(renk)

    # İndirilecek format seçimi
    format_secimi = st.selectbox("Çıktı formatı seçin:", ("STL", "PLY", "GLB"))

    if st.button("Modeli Oluştur ve İndir"):
        zaman_etiketi = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        dosya_adi = f"model_{zaman_etiketi}.{format_secimi.lower()}"
        hedef_yol = cikti_dizini / dosya_adi

        if model_sahne is not None:
            # Sahne bazlı çıktı (genellikle GLB için uygundur)
            sahne = model_sahne.copy()
            if olcek != 1.0:
                sahne.apply_scale(olcek)

            if format_secimi == "STL":
                sahne.export(str(hedef_yol), file_type="stl")
            else:
                sahne.export(str(hedef_yol), file_type=format_secimi.lower())

        else:
            mesh = model_mesh.copy()
            mesh.apply_scale(olcek)

            if format_secimi == "STL":
                # STL formatı renk bilgisi taşımaz.
                mesh.export(str(hedef_yol), file_type="stl")
            else:
                mesh_renkli_kaydet(
                    mesh,
                    str(hedef_yol),
                    dosya_tipi=format_secimi.lower(),
                    renk=renk_rgb,
                    metalik=metalik,
                    pürüzlülük=pürüzlülük,
                )

        with open(hedef_yol, "rb") as stl_dosyasi:
            st.download_button(
                label=f"{format_secimi} dosyasını indir",
                data=stl_dosyasi.read(),
                file_name=dosya_adi,
                mime="application/octet-stream",
            )

        st.success(f"Model dosyası oluşturuldu: {dosya_adi}")

        # Oluşturulan modelin hızlı önizlemesi (GLB kullanarak)
        try:
            if model_sahne is not None:
                glb_uri = scene_to_glb_data_uri(model_sahne)
            else:
                glb_uri = mesh_to_glb_data_uri(mesh)

            components.html(
                _onizleme_html(
                    glb_uri,
                    wireframe=wireframe,
                    show_ground=show_ground,
                    ambient_intensity=ambient_intensity,
                    directional_intensity=directional_intensity,
                ),
                height=450,
            )
        except Exception:
            pass
