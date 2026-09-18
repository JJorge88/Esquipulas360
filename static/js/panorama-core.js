/* Shared geometry and camera conventions for the public viewer and private editor. */
(() => {
  'use strict';
  if (!window.AFRAME) return;
  const THREE = AFRAME.THREE;
  // Canvas labels avoid remote font requests; every label is a real WebGL object in VR.
  AFRAME.registerComponent('tour-label', {
    schema: { text: { default: '' }, width: { default: 1 }, height: { default: 0.26 }, accent: { default: false } },
    init() {
      this.canvas = document.createElement('canvas');
      this.canvas.width = 1024; this.canvas.height = 256;
      this.texture = new THREE.CanvasTexture(this.canvas);
      this.texture.colorSpace = THREE.SRGBColorSpace;
      this.material = new THREE.MeshBasicMaterial({ map: this.texture, transparent: true, side: THREE.DoubleSide });
      this.geometry = new THREE.PlaneGeometry(this.data.width, this.data.height);
      this.el.setObject3D('mesh', new THREE.Mesh(this.geometry, this.material));
    },
    update() {
      const ctx = this.canvas.getContext('2d');
      ctx.clearRect(0, 0, 1024, 256);
      ctx.fillStyle = this.data.accent ? '#fece57' : '#132238';
      ctx.beginPath(); ctx.roundRect(0, 0, 1024, 256, 30); ctx.fill();
      ctx.strokeStyle = '#8796a5'; ctx.lineWidth = 4; ctx.stroke();
      ctx.fillStyle = this.data.accent ? '#132238' : '#fbf9f6';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      let size = 70;
      do { ctx.font = `600 ${size}px sans-serif`; size -= 2; } while (ctx.measureText(this.data.text).width > 940 && size > 16);
      ctx.fillText(this.data.text, 512, 128);
      this.texture.needsUpdate = true;
    },
    remove() { this.texture.dispose(); this.material.dispose(); this.geometry.dispose(); this.el.removeObject3D('mesh'); }
  });
  AFRAME.registerComponent('tour-face-camera', {
    init() { this.target = new THREE.Vector3(); },
    tick() { if (this.el.sceneEl.camera) { this.el.sceneEl.camera.getWorldPosition(this.target); this.el.object3D.lookAt(this.target); } }
  });


  const position = (yaw, pitch, radius = 3.5) => {
    const y = THREE.MathUtils.degToRad(yaw), p = THREE.MathUtils.degToRad(pitch);
    return new THREE.Vector3(-radius * Math.sin(y) * Math.cos(p), radius * Math.sin(p), -radius * Math.cos(y) * Math.cos(p));
  };
  const angles = direction => {
    const d = direction.clone().normalize();
    return { yaw: THREE.MathUtils.radToDeg(Math.atan2(-d.x, -d.z)), pitch: THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(d.y, -1, 1))) };
  };
  function setOrientation(scene, rig, camera, orientation) {
    rig.object3D.rotation.set(0, THREE.MathUtils.degToRad(orientation.yaw), 0);
    const look = camera.components['look-controls'];
    if (look) {
      look.yawObject.rotation.y = 0;
      look.pitchObject.rotation.x = THREE.MathUtils.degToRad(orientation.pitch);
    }
    if (!scene.renderer.xr.isPresenting) camera.object3D.rotation.set(THREE.MathUtils.degToRad(orientation.pitch), 0, 0);
    scene.object3D.updateMatrixWorld(true);
    scene.camera.updateMatrixWorld(true);
  }
  function currentOrientation(scene) {
    scene.object3D.updateMatrixWorld(true);
    return angles(scene.camera.getWorldDirection(new THREE.Vector3()));
  }
  function touchPitch(scene, camera) {
    let touchY = null;
    scene.canvas.addEventListener('touchstart', event => {
      touchY = event.touches.length === 1 && !scene.is('vr-mode') ? event.touches[0].clientY : null;
    }, { passive: true });
    scene.canvas.addEventListener('touchmove', event => {
      if (touchY === null || event.touches.length !== 1 || scene.is('vr-mode')) return;
      const y = event.touches[0].clientY;
      const pitch = camera.components['look-controls'].pitchObject.rotation;
      pitch.x = THREE.MathUtils.clamp(pitch.x - (y - touchY) * Math.PI / scene.canvas.clientHeight, -Math.PI / 2, Math.PI / 2);
      touchY = y;
      event.preventDefault();
    }, { passive: false });
    const endTouch = () => { touchY = null; };
    scene.canvas.addEventListener('touchend', endTouch);
    scene.canvas.addEventListener('touchcancel', endTouch);
  }
  function worldQuaternion(scene) {
    const result = new THREE.Quaternion();
    if (scene.renderer.xr.isPresenting) {
      // Sample after rendering (tock). WebXRManager has already composed the tracked
      // head pose with the camera parent's world transform, including our rig.
      // Do not apply the rig again or read look-controls Euler angles in immersive VR.
      const xrCamera = scene.renderer.xr.getCamera();
      const rotation = new THREE.Matrix4().extractRotation(xrCamera.matrixWorld);
      return result.setFromRotationMatrix(rotation).normalize();
    }
    scene.camera.getWorldQuaternion(result);
    return result.normalize();
  }
  AFRAME.registerComponent('stand-transition', {
    schema: { active: { default: false } },
    init() {
      this.opacity = 0;
      this.veil = new THREE.Mesh(new THREE.SphereGeometry(.4, 24, 16), new THREE.MeshBasicMaterial({color: '#132238', side: THREE.BackSide, transparent: true, opacity: 0, depthTest: false, depthWrite: false}));
      this.veil.renderOrder = 1000;
      this.el.camera.add(this.veil);
    },
    tick(time, delta) {
      const target = this.data.active ? 1 : 0;
      this.opacity += THREE.MathUtils.clamp(target - this.opacity, -delta / 160, delta / 160);
      this.veil.material.opacity = this.opacity;
      this.veil.visible = this.opacity > .001;
    },
    remove() { this.veil.removeFromParent(); this.veil.geometry.dispose(); this.veil.material.dispose(); }
  });
  window.PanoramaTools = { position, angles, setOrientation, currentOrientation, touchPitch, worldQuaternion };
})();
