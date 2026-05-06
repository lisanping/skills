"""浏览器 3D 交互查看器 — STEP → GLB → Three.js.

用法:
    python -m aec_building.tools.viewer_3d                               # 最新模型
    python -m aec_building.tools.viewer_3d output/*/model.step           # 指定文件
    python -m aec_building.tools.viewer_3d --port 9000 model.step        # 自定义端口
"""

from __future__ import annotations

import http.server
import os
import sys
import threading
import webbrowser
from pathlib import Path

from aec_building.utils.output import find_latest_step, step_to_glb


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ margin: 0; overflow: hidden; background: {bg_color}; }}
  #info {{ position: absolute; top: 10px; left: 10px; color: #333; font: 14px sans-serif;
           background: rgba(255,255,255,0.85); padding: 8px 14px; border-radius: 6px; border: 1px solid #ccc; }}
</style>
</head><body>
<div id="info">{title} — drag to rotate, scroll to zoom, right-click to pan</div>
<script type="importmap">
{{ "imports": {{
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
}} }}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ GLTFLoader }} from 'three/addons/loaders/GLTFLoader.js';

const scene = new THREE.Scene();
scene.background = new THREE.Color('{bg_hex}');

// 天空光 (环境光)
scene.add(new THREE.AmbientLight(0xffffff, 0.5));

// 主方向光 (太阳) + 阴影
const sunLight = new THREE.DirectionalLight(0xfffbe8, 1.2);
sunLight.position.set(1, 2, 1.5);
sunLight.castShadow = true;
sunLight.shadow.mapSize.width = 2048;
sunLight.shadow.mapSize.height = 2048;
scene.add(sunLight);

// 补光
const fillLight = new THREE.DirectionalLight(0x8899bb, 0.4);
fillLight.position.set(-1, 0.5, -1);
scene.add(fillLight);

// 半球光 (天地过渡)
const hemiLight = new THREE.HemisphereLight(0xddeeff, 0x998866, 0.3);
scene.add(hemiLight);

const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 1, 500000);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

new GLTFLoader().load('{glb_url}', (gltf) => {{
  const model = gltf.scene;

  // 升级材质: 为每个网格启用 PBR
  model.traverse((node) => {{
    if (node.isMesh) {{
      node.castShadow = true;
      node.receiveShadow = true;

      // 修复缺失法线 — trimesh GLB 导出可能不含 NORMAL 属性
      if (!node.geometry.attributes.normal) {{
        node.geometry.computeVertexNormals();
      }}

      // 保留 GLB 中的顶点颜色
      const oldMat = node.material;
      const hasVertexColors = node.geometry.attributes.color !== undefined;
      const newMat = new THREE.MeshStandardMaterial({{
        vertexColors: hasVertexColors,
        color: hasVertexColors ? 0xffffff : (oldMat.color || new THREE.Color(0xcccccc)),
        metalness: 0.1,
        roughness: 0.7,
        side: THREE.DoubleSide,
      }});

      // 半透明处理
      if (oldMat.opacity < 1.0 || (oldMat.transparent)) {{
        newMat.transparent = true;
        newMat.opacity = oldMat.opacity || 0.4;
        newMat.depthWrite = false;
      }}

      node.material = newMat;
    }}
  }});

  scene.add(model);
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  model.position.sub(center);
  controls.target.set(0, 0, 0);
  camera.position.set(size * 0.8, size * 0.6, size * 0.8);
  camera.near = size * 0.001;
  camera.far = size * 10;
  camera.updateProjectionMatrix();

  // 调整阴影范围
  sunLight.shadow.camera.left = -size;
  sunLight.shadow.camera.right = size;
  sunLight.shadow.camera.top = size;
  sunLight.shadow.camera.bottom = -size;
  sunLight.shadow.camera.near = 0.1;
  sunLight.shadow.camera.far = size * 5;
  sunLight.shadow.camera.updateProjectionMatrix();

  controls.update();
}});

window.addEventListener('resize', () => {{
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}});

function animate() {{
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}}
animate();
</script>
</body></html>"""


def serve_and_open(
    glb_path: Path,
    port: int = 8765,
    background: str = "#f0f2f5",
):
    """启动本地 HTTP 服务器并在浏览器中打开 3D 查看器.

    Args:
        glb_path: GLB 文件路径。
        port: HTTP 端口。
        background: 背景色 CSS。
    """
    serve_dir = glb_path.parent
    title = serve_dir.name or glb_path.stem

    html_content = HTML_TEMPLATE.format(
        title=title,
        glb_url=glb_path.name,
        bg_color=background,
        bg_hex=background,
    )
    html_path = serve_dir / "viewer.html"
    html_path.write_text(html_content, encoding="utf-8")

    os.chdir(serve_dir)
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None

    httpd = http.server.HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/viewer.html"
    print(f"\n3D Viewer: {url}")
    print("Press Ctrl+C to stop\n")
    webbrowser.open(url)

    try:
        thread.join()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="STEP 文件 3D 交互查看器")
    parser.add_argument("step_file", nargs="?", help="STEP 文件路径")
    parser.add_argument("--port", type=int, default=8765, help="HTTP 端口")
    parser.add_argument("--bg", default="#f0f2f5", help="背景色")
    args = parser.parse_args()

    if args.step_file:
        step_path = Path(args.step_file)
    else:
        step_path = find_latest_step()
        if not step_path:
            print("No STEP file found. Usage: python -m aec_building.tools.viewer_3d <file.step>")
            sys.exit(1)

    print(f"Loading: {step_path}")
    glb_path = step_to_glb(step_path)
    print(f"GLB: {glb_path} ({glb_path.stat().st_size // 1024} KB)")
    serve_and_open(glb_path, port=args.port, background=args.bg)


if __name__ == "__main__":
    main()
