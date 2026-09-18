import { test, expect } from '@playwright/test';

const demo = '/recorridos/demostracion/';
const databaseTour = async request => {
  const response = await request.get(demo);
  const html = await response.text();
  return JSON.parse(html.match(/<script id="tour-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
};
const ready = async page => {
  await page.goto(demo);
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await expect(page.locator('#viewer-status')).toBeHidden();
};

test('home, original logo, honest content and catalog navigation', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Descubre Esquipulas');
  await expect(page.getByText('Vista desde el mirador · imagen pendiente')).toBeVisible();
  await expect(page.locator('.brand img')).toHaveJSProperty('naturalWidth', 1254);
  await expect(page.locator('.tour-card a')).toHaveCount(0);
  await page.screenshot({ path: 'artifacts/home-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Explorar lugares' }).click();
  await expect(page.locator('.tour-card')).toHaveCount(4);
  await page.screenshot({ path: 'artifacts/explore-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('search ignores accents and case, category composes and reset works', async ({ page }) => {
  await page.goto('/explorar/');
  await page.getByRole('searchbox').fill('BASILICA');
  await page.getByRole('button', { name: 'Buscar', exact: false }).click();
  await expect(page.locator('.tour-card')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Basílica', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Patrimonio', exact: true }).click();
  await expect(page.locator('.tour-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Vistas', exact: true }).click();
  await expect(page.getByText('Aún no encontramos esa mirada.')).toBeVisible();
  await page.getByRole('link', { name: 'Restablecer búsqueda' }).click();
  await expect(page.locator('.tour-card')).toHaveCount(4);
  await page.getByRole('searchbox').fill('basílica');
  await page.getByRole('searchbox').press('Enter');
  await expect(page.locator('.tour-card')).toHaveCount(1);
});

test('mobile menu and responsive layouts at 360, 390 and 768 px', async ({ page }) => {
  for (const width of [360, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of ['/', '/explorar/']) {
      await page.goto(path);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.getByRole('button', { name: 'Abrir menú' }).click();
      await expect(page.getByRole('navigation')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('navigation')).toBeHidden();
      if (width === 390) await page.screenshot({ path: `artifacts/${path === '/' ? 'home' : 'explore'}-mobile.png`, fullPage: true });
    }
  }
});

test('real spherical panorama, lazy second scene, selector, orientation and cleanup', async ({ page }) => {
  const errors = [], failedRequests = [], panoramaRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', request => failedRequests.push(request.url()));
  page.on('request', request => { if (request.url().includes('/panoramas/')) panoramaRequests.push(request.url()); });
  await ready(page);
  const data = JSON.parse(await page.locator('#tour-data').textContent());
  expect(panoramaRequests.some(url => url.endsWith(data.scenes[1].panorama))).toBe(false);
  await expect(page.locator('#info-panel')).toBeHidden();
  await expect(page.locator('audio')).toHaveCount(0);
  const geometry = await page.locator('#panorama-sky').evaluate(el => {
    const mesh = el.getObject3D('mesh');
    return { type: mesh.geometry.type, width: mesh.material.map.image.naturalWidth, height: mesh.material.map.image.naturalHeight };
  });
  expect(geometry).toEqual({ type: 'SphereGeometry', width: 2048, height: 1024 });
  await page.evaluate(() => {
    window.disposedTextures = 0;
    document.querySelector('#panorama-sky').getObject3D('mesh').material.map.addEventListener('dispose', () => window.disposedTextures++);
  });
  await page.screenshot({ path: 'artifacts/viewer-desktop.png' });
  await page.getByRole('combobox', { name: 'Seleccionar escena' }).selectOption('ambar');
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'ambar');
  expect(await page.evaluate(() => window.disposedTextures)).toBe(1);
  const rotation = await page.locator('#camera-rig').evaluate(el => el.object3D.rotation.y);
  expect(rotation).toBeCloseTo(Math.PI / 2);
  await page.getByRole('button', { name: 'Volver a escena azul' }).click();
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  expect(errors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test('pointer hotspot changes scenes and supports returning', async ({ page }) => {
  await ready(page);
  await page.mouse.click(720, 500);
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'ambar');
  // Project the return marker through the actual camera, then click the WebGL canvas.
  const position = await page.locator('[data-hotspot="a-azul"]').evaluate(el => {
    const scene = el.sceneEl;
    const point = new AFRAME.THREE.Vector3();
    el.object3D.getWorldPosition(point); point.project(scene.camera);
    const box = scene.canvas.getBoundingClientRect();
    return { x: box.left + (point.x + 1) / 2 * box.width, y: box.top + (1 - point.y) / 2 * box.height };
  });
  await page.mouse.move(position.x, position.y);
  await expect.poll(() => page.locator('#panorama-scene').evaluate(el => el.components.cursor.intersectedEl?.closest('[data-hotspot]')?.dataset.hotspot)).toBe('a-azul');
  await page.mouse.click(position.x, position.y);
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
});

test('mouse looks all around and up/down without moving the camera', async ({ page }) => {
  await ready(page);
  for (let i = 0; i < 8; i++) {
    await page.mouse.move(1150, 430); await page.mouse.down();
    await page.mouse.move(240, 430, { steps: 6 }); await page.mouse.up();
  }
  let rotations = await page.locator('#tour-camera').evaluate(el => ({ yaw: el.components['look-controls'].yawObject.rotation.y, pitch: el.components['look-controls'].pitchObject.rotation.x }));
  expect(Math.abs(rotations.yaw)).toBeGreaterThan(Math.PI * 2);
  await page.mouse.move(800, 250); await page.mouse.down(); await page.mouse.move(800, 720, { steps: 6 }); await page.mouse.up();
  rotations = await page.locator('#tour-camera').evaluate(el => ({ pitch: el.components['look-controls'].pitchObject.rotation.x, position: el.object3D.position.toArray() }));
  expect(Math.abs(rotations.pitch)).toBeGreaterThan(.4);
  expect(rotations.position).toEqual([0, 0, 0]);
});

test('missing panorama reports an error and retry recovers', async ({ page, request }) => {
  const url = '**' + (await databaseTour(request)).scenes[0].panorama;
  await page.route(url, route => route.fulfill({ status: 404, body: 'Missing' }));
  await page.goto(demo);
  await expect(page.getByRole('heading', { name: 'No pudimos abrir esta escena' })).toBeVisible();
  await expect(page.locator('#main')).toHaveAttribute('data-loading', 'error');
  await page.unroute(url);
  await page.getByRole('button', { name: 'Volver a intentar' }).click();
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await expect(page.locator('#viewer-status')).toBeHidden();
});

test('second scene load failure can recover while retaining current texture', async ({ page, request }) => {
  await ready(page);
  const url = '**' + (await databaseTour(request)).scenes[1].panorama;
  await page.route(url, route => route.fulfill({ status: 404, body: 'Missing' }));
  await page.getByRole('combobox').selectOption('ambar');
  await expect(page.getByRole('heading', { name: 'No pudimos abrir esta escena' })).toBeVisible();
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await page.unroute(url);
  await page.getByRole('button', { name: 'Volver a intentar' }).click();
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'ambar');
});

test('viewer honors inclusive panorama ratio limits and rejects an outside image', async ({ page, request }) => {
  const url = '**' + (await databaseTour(request)).scenes[0].panorama;
  await page.goto('/');
  for (const width of [1980, 2020, 1979]) {
    const base64 = await page.evaluate(width => {
      const canvas = document.createElement('canvas');
      canvas.width = width; canvas.height = 1000;
      canvas.getContext('2d').fillRect(0, 0, width, 1000);
      return canvas.toDataURL('image/png').split(',')[1];
    }, width);
    await page.route(url, route => route.fulfill({ contentType: 'image/png', body: Buffer.from(base64, 'base64') }));
    await page.goto(demo);
    if (width === 1979) {
      await expect(page.getByRole('heading', { name: 'No pudimos abrir esta escena' })).toBeVisible();
      await expect(page.locator('#main')).toHaveAttribute('data-loading', 'error');
    } else {
      await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
      await expect(page.locator('#viewer-status')).toBeHidden();
      expect(await page.locator('#panorama-sky').evaluate(el => el.getObject3D('mesh').material.map.image.naturalWidth)).toBe(width);
    }
    await page.unroute(url);
  }
});

test('unsupported VR has a usable normal view and essential VR controls exist', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'xr', { value: undefined, configurable: true }));
  await ready(page);
  await expect(page.getByRole('button', { name: 'VR no disponible', exact: true })).toBeDisabled();
  await expect(page.locator('#vr-message')).toContainText('pantalla normal');
  await expect(page.locator('#vr-navigation [data-action="explore"]')).toHaveCount(1);
  await expect(page.locator('#vr-navigation [data-action="exit"]')).toHaveCount(1);
  await expect(page.locator('#vr-navigation [data-action^="scene:"]')).toHaveCount(2);
  await expect(page.locator('#right-controller')).toHaveAttribute('laser-controls', /hand: right/);
  await expect(page.locator('.a-enter-vr')).toHaveCount(0);
  await page.getByRole('button', { name: 'Información del recorrido' }).click();
  await expect(page.locator('#info-panel')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#info-panel')).toBeHidden();
});

test('VR permission rejection is recoverable and requests occur only on click (mock)', async ({ page }) => {
  await page.addInitScript(() => {
    const xr = new EventTarget();
    xr.isSessionSupported = async () => true;
    window.xrRequests = 0;
    xr.requestSession = async () => { window.xrRequests++; throw new DOMException('Denied by test', 'NotAllowedError'); };
    Object.defineProperty(navigator, 'xr', { value: xr, configurable: true });
  });
  await ready(page);
  await expect(page.getByRole('button', { name: 'Entrar en VR', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => window.xrRequests)).toBe(0);
  await page.evaluate(() => navigator.xr.dispatchEvent(new Event('sessiongranted')));
  expect(await page.evaluate(() => window.xrRequests)).toBe(0);
  await page.getByRole('button', { name: 'Entrar en VR', exact: true }).click();
  await expect(page.locator('#vr-message')).toContainText('denegado o cancelado');
  await expect(page.getByRole('button', { name: 'Entrar en VR', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => window.xrRequests)).toBe(1);
});

test('mobile viewer fits and touch gestures rotate the panorama', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8000' + demo);
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const session = await context.newCDPSession(page);
  await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 300, y: 370 }] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 80, y: 470 }] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  const yaw = await page.locator('#tour-camera').evaluate(el => el.components['look-controls'].yawObject.rotation.y);
  expect(Math.abs(yaw)).toBeGreaterThan(.2);
  const pitchDown = await page.locator('#tour-camera').evaluate(el => el.components['look-controls'].pitchObject.rotation.x);
  expect(pitchDown).toBeLessThan(-.2);
  await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y: 600 }] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 200, y: 250 }] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  const pitchUp = await page.locator('#tour-camera').evaluate(el => el.components['look-controls'].pitchObject.rotation.x);
  expect(pitchUp).toBeGreaterThan(.4);
  await page.screenshot({ path: 'artifacts/viewer-mobile.png' });
  await page.getByRole('combobox').selectOption('ambar');
  await expect(page.locator('#main')).toHaveAttribute('data-scene', 'ambar');
  expect(errors).toEqual([]);
  await context.close();
});

test('fullscreen control enters and leaves fullscreen', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: 'Pantalla completa', exact: true }).click();
  await expect(page.locator('#fullscreen')).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Salir de pantalla completa', exact: true }).click();
  await expect(page.locator('#fullscreen')).toHaveAttribute('aria-pressed', 'false');
});
