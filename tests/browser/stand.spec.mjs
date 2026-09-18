import { test as base, expect } from '@playwright/test';
import fs from 'node:fs';
const origin = 'http://127.0.0.1:8016';
const manifest = () => JSON.parse(fs.readFileSync('artifacts/stand-session.json', 'utf8'));

const test = base.extend({ stand: async ({ browser }, use) => {
  const data = manifest(), contexts = [];
  const context = async () => { const c = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 1000 } }); contexts.push(c); return c; };
  const operatorContext = await context();
  await operatorContext.addCookies([{ name: 'sessionid', value: data.cookie, domain: '127.0.0.1', path: '/' }]);
  const operator = await operatorContext.newPage();
  const errors = [];
  operator.on('pageerror', e => errors.push(e.message));
  await operator.goto('/panel/stand/');
  await expect(operator.locator('#stand-tour')).not.toContainText('Borrador privado');
  await operator.locator('#stand-tour').selectOption(String(data.demo));
  await operator.getByRole('button', { name: 'Crear sesión', exact: true }).click();
  await expect(operator.locator('#stand-network')).toContainText('Conexión activa');
  const sid = operator.url().match(/stand\/([^/]+)\//)[1];
  const code = await operator.locator('#pair-code').innerText();
  const join = async () => {
    const c = await context(), page = await c.newPage();
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('/stand/');
    await page.getByLabel('Código de vinculación').fill(code);
    await page.getByRole('button', { name: 'Vincular visor' }).click();
    await expect(page).toHaveURL(new RegExp(`/stand/${sid}/viewer/`));
    await expect(operator.locator('#viewer-presence')).toContainText('Visor conectado');
    return page;
  };
  const spectator = async () => {
    // Issue through the real CSRF-protected action, then use only its scoped cookie
    // in an independent browser context. The TV never needs an admin session.
    const csrf = (await operatorContext.cookies()).find(c => c.name === 'csrftoken').value;
    const response = await operatorContext.request.post(`/panel/stand/${sid}/spectator/`, { headers: { 'X-CSRFToken': csrf } });
    expect(response.ok()).toBeTruthy();
    const cookie = (await operatorContext.cookies(origin + `/stand/${sid}/`)).find(c => c.name.startsWith('stand_spectator_'));
    const c = await context(); await c.addCookies([cookie]);
    const page = await c.newPage(); page.on('pageerror', e => errors.push(e.message));
    await page.goto(`/stand/${sid}/spectator/`);
    await expect(operator.locator('#spectator-presence')).toContainText('Espectador conectado');
    return page;
  };
  const start = async () => { await operator.getByRole('button', { name: 'Iniciar recorrido', exact: true }).click(); await expect(operator.locator('#stand-order')).toContainText('aplicada'); };
  const actual = async (viewer, tv, key) => {
    await expect(viewer.locator('#main')).toHaveAttribute('data-scene', key);
    await expect(viewer.locator('#main')).toHaveAttribute('data-loading', 'false');
    await expect(operator.locator('#stand-order')).toContainText('aplicada');
    if (tv) await expect(tv.locator('#main')).toHaveAttribute('data-scene', key);
  };
  try { await use({ data, operator, operatorContext, code, sid, context, join, spectator, start, actual, errors }); }
  finally {
    const csrf = (await operatorContext.cookies()).find(c => c.name === 'csrftoken')?.value;
    const snapshot = await operatorContext.request.get(`/stand/${sid}/state/operator/`);
    if (snapshot.ok()) {
      const state = await snapshot.json();
      if (state.type !== 'ended') await operatorContext.request.post(`/panel/stand/${sid}/command/`, { headers: { 'X-CSRFToken': csrf }, data: { id: crypto.randomUUID(), seq: state.seq, action: 'end', tour: data.demo, scene: null } });
    }
    for (const c of contexts.reverse()) await c.close();
  }
} });

async function quaternion(page, selector) {
  return page.evaluate(sel => {
    const scene = document.querySelector(sel);
    return PanoramaTools.worldQuaternion(scene).toArray();
  }, selector);
}
const angle = (a, b) => 2 * Math.acos(Math.min(1, Math.abs(a.reduce((s, n, i) => s + n * b[i], 0))));

// All three roles run concurrently in separate contexts, without shared admin cookies.
test('vinculación, inicio, navegación bidireccional, cambio de recorrido y reinicio', async ({ stand: s }) => {
  const viewer = await s.join(), tv = await s.spectator();
  await expect(tv.locator('#spectator-waiting')).toBeVisible();
  await expect(viewer.locator('#status-title')).toHaveText('Listo para el stand');
  expect((await viewer.context().cookies()).some(c => c.name === 'sessionid')).toBe(false);
  expect((await tv.context().cookies()).some(c => c.name === 'sessionid')).toBe(false);
  await viewer.evaluate(() => {
    const scene = document.querySelector('#panorama-scene'), original = scene.enterVR.bind(scene);
    window.standTestVRRequests = 0;
    scene.enterVR = (...args) => { ++window.standTestVRRequests; return original(...args); };
  });
  await s.start(); await s.actual(viewer, tv, 'azul');
  await s.operator.locator('[data-scene="ambar"]').click(); await s.actual(viewer, tv, 'ambar');
  await viewer.locator('#scene-select').selectOption('azul'); await s.actual(viewer, tv, 'azul');
  await viewer.locator('#next-hotspot').click(); await s.actual(viewer, tv, 'ambar');
  await s.operator.getByRole('button', { name: 'Volver al inicio', exact: true }).click(); await s.actual(viewer, tv, 'azul');
  await s.operator.locator('#operator-tour').selectOption(String(s.data.other));
  await s.operator.getByRole('button', { name: 'Cambiar recorrido', exact: true }).click(); await s.actual(viewer, tv, 'otra');
  await expect(s.operator.locator('#confirmed-tour')).toHaveText('Recorrido alternativo');
  await expect(tv.locator('#spectator-title')).toContainText('Otra perspectiva');
  expect(await viewer.evaluate(() => window.standTestVRRequests)).toBe(0);
  expect(s.errors).toEqual([]);
});

test('código caducado, uso único y segundo visor no reemplaza al primero', async ({ stand: s }) => {
  const invalidContext = await s.context(), invalid = await invalidContext.newPage();
  await invalid.goto('/stand/');
  await invalid.getByLabel('Código de vinculación').fill(s.data.expiredCode);
  await invalid.getByRole('button', { name: 'Vincular visor' }).click();
  await expect(invalid.getByRole('alert')).toContainText('caducó');
  const viewer = await s.join();
  await invalid.getByLabel('Código de vinculación').fill(s.code);
  await invalid.getByRole('button', { name: 'Vincular visor' }).click();
  await expect(invalid.getByRole('alert')).toContainText('ya fue utilizado');
  const duplicate = await viewer.context().newPage(); await duplicate.goto(viewer.url());
  await expect(duplicate.locator('#stand-connection')).toContainText('otra ventana');
  await duplicate.close();
  await s.start(); await s.actual(viewer, null, 'azul');
  expect(s.errors).toEqual([]);
});

test('mirada suave, cruce de 180°, cámara XR simulada y sin rotación impuesta al cambiar', async ({ stand: s }) => {
  const viewer = await s.join(), tv = await s.spectator(); await s.start(); await s.actual(viewer, tv, 'azul');
  const look = async (yaw, pitch) => {
    const target = await viewer.evaluate(({ yaw, pitch }) => {
      const look = document.querySelector('#tour-camera').components['look-controls'];
      look.yawObject.rotation.y = yaw * Math.PI / 180; look.pitchObject.rotation.x = pitch * Math.PI / 180;
      return new AFRAME.THREE.Quaternion().setFromEuler(new AFRAME.THREE.Euler(pitch * Math.PI / 180, yaw * Math.PI / 180, 0, 'YXZ')).toArray();
    }, { yaw, pitch });
    // Wait for the A-Frame tick to apply the requested look before comparing clients.
    await expect.poll(async () => angle(target, await quaternion(viewer, '#panorama-scene'))).toBeLessThan(.005);
    await expect.poll(async () => angle(target, await quaternion(tv, '#spectator-scene'))).toBeLessThan(.03);
  };
  await look(179, 20);
  await look(-179, 20);
  const before = await quaternion(viewer, '#panorama-scene');
  await s.operator.locator('[data-scene="ambar"]').click(); await s.actual(viewer, tv, 'ambar');
  expect(angle(before, await quaternion(viewer, '#panorama-scene'))).toBeLessThan(.005);
  const xr = await viewer.evaluate(() => {
    const T = AFRAME.THREE;
    const rig = new T.Quaternion().setFromEuler(new T.Euler(0, .8, 0));
    const head = new T.Quaternion().setFromEuler(new T.Euler(.3, -.6, .2, 'YXZ'));
    const expected = rig.clone().multiply(head);
    const matrixWorld = new T.Matrix4().compose(new T.Vector3(), expected, new T.Vector3(1, 1, 1));
    const sampled = PanoramaTools.worldQuaternion({ renderer: { xr: { isPresenting: true, getCamera: () => ({ matrixWorld }) } } });
    return sampled.angleTo(expected);
  });
  expect(xr).toBeLessThan(.000001); // Mathematical simulation, not a physical Quest validation.
  await tv.mouse.move(700, 400); await tv.mouse.down(); await tv.mouse.move(1100, 500, { steps: 10 }); await tv.mouse.up();
  expect(angle(before, await quaternion(viewer, '#panorama-scene'))).toBeLessThan(.005);
  expect(s.errors).toEqual([]);
});

test('pérdida de red conserva imagen y recupera solo el estado vigente', async ({ stand: s }) => {
  const viewer = await s.join(), tv = await s.spectator(); await s.start(); await s.actual(viewer, tv, 'azul');
  // Close transport and block subsequent WebSocket connections through CDP network emulation.
  const cdp = await viewer.context().newCDPSession(viewer);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await expect(s.operator.locator('#viewer-presence')).toContainText('Desconectado', { timeout: 25000 });
  await expect(viewer.locator('#stand-connection')).toContainText(/conexión|Conexión/);
  await expect(viewer.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await expect(tv.locator('#spectator-status')).toContainText(/desconectado|actualizando/);
  await s.operator.locator('[data-scene="ambar"]').click();
  await expect(s.operator.locator('#desired-scene')).toContainText('ámbar');
  await expect(s.operator.locator('#stand-order')).toContainText('Esperando confirmación');
  await s.operator.locator('[data-scene="azul"]').click();
  await expect(s.operator.locator('#desired-scene')).toContainText('azul');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await s.actual(viewer, tv, 'azul');
  await expect(s.operator.locator('#viewer-presence')).toContainText('Visor conectado');
  await s.operator.locator('[data-scene="ambar"]').click(); await s.actual(viewer, tv, 'ambar');
  expect(s.errors).toEqual([]);
});

test('error de imagen, confirmación real y reintento sin perder escena anterior', async ({ stand: s }) => {
  const viewer = await s.join(), tv = await s.spectator(); await s.start(); await s.actual(viewer, tv, 'azul');
  const before = await s.operator.locator('#confirmed-scene').innerText();
  await viewer.route('**/panorama/*/', route => route.fulfill({ status: 503, body: 'test' }));
  await s.operator.locator('[data-scene="ambar"]').click();
  await expect(s.operator.locator('#stand-order')).toContainText('Error del visor');
  await expect(s.operator.locator('#confirmed-scene')).toHaveText(before);
  await expect(tv.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await viewer.unroute('**/panorama/*/');
  await viewer.getByRole('button', { name: 'Volver a intentar' }).click();
  await s.actual(viewer, tv, 'ambar');
  // Simulate the browser's graphics-loss notification; CPU decoding must not ACK
  // another scene while the renderer is unavailable.
  await viewer.evaluate(() => document.querySelector('#panorama-scene').canvas.dispatchEvent(new Event('webglcontextlost', { cancelable: true })));
  await expect(s.operator.locator('#stand-order')).toContainText('Error del visor');
  await s.operator.locator('[data-scene="azul"]').click();
  await expect(s.operator.locator('#desired-scene')).toContainText('azul');
  await expect(s.operator.locator('#stand-order')).toContainText('Error del visor');
  await expect(s.operator.locator('#confirmed-scene')).toContainText('ámbar');
  expect(s.errors).toEqual([]);
});

test('roles aislados, pantalla sin controles, finalización y credenciales revocadas', async ({ stand: s }) => {
  const viewer = await s.join(), tv = await s.spectator(); await s.start(); await s.actual(viewer, tv, 'azul');
  for (const page of [viewer, tv]) {
    expect((await page.request.get(`/stand/${s.sid}/state/operator/`)).status()).toBe(403);
    expect((await page.request.post(`/panel/stand/${s.sid}/command/`, { data: {} })).status()).toBe(403);
  }
  expect((await tv.request.get(`/stand/${s.sid}/viewer/`)).status()).toBe(403);
  expect((await viewer.request.get(`/stand/${s.sid}/spectator/`)).status()).toBe(403);
  await expect(tv.locator('#scene-select, #enter-vr, [data-action], .panel-sidebar')).toHaveCount(0);
  await tv.getByRole('button', { name: 'Pantalla completa', exact: true }).click();
  await expect(tv.getByRole('button', { name: 'Salir de pantalla completa' })).toBeVisible();
  s.operator.once('dialog', dialog => dialog.accept());
  await s.operator.getByRole('button', { name: 'Finalizar sesión' }).click();
  await expect(viewer.locator('#status-title')).toHaveText('Sesión finalizada');
  await expect(tv.locator('#spectator-waiting h1')).toHaveText('Gracias por explorar');
  expect((await viewer.request.get(`/stand/${s.sid}/state/viewer/`)).status()).toBe(403);
  expect((await tv.request.get(`/stand/${s.sid}/state/spectator/`)).status()).toBe(403);
  expect(s.errors).toEqual([]);
});

test('interfaz móvil, ventana pública real y capturas de las tres pantallas', async ({ stand: s }) => {
  const viewer = await s.join(); await s.start(); await s.actual(viewer, null, 'azul');
  const popupPromise = s.operator.waitForEvent('popup');
  await s.operator.getByRole('button', { name: 'Abrir pantalla del público' }).click();
  const tv = await popupPromise;
  await expect(tv.locator('#main')).toHaveAttribute('data-scene', 'azul');
  fs.mkdirSync('artifacts/phase5', { recursive: true });
  await s.operator.screenshot({ path: 'artifacts/phase5/operador.png', fullPage: true });
  await viewer.screenshot({ path: 'artifacts/phase5/participante.png' });
  await tv.screenshot({ path: 'artifacts/phase5/espectador.png' });
  const replacementPromise = s.operator.waitForEvent('popup');
  await s.operator.getByRole('button', { name: 'Abrir pantalla del público' }).click();
  const replacement = await replacementPromise;
  await expect(replacement.locator('#main')).toHaveAttribute('data-scene', 'azul');
  await expect(tv.locator('#spectator-status')).toContainText(/otra ventana|finalizada|acceso/);
  await replacement.close();
  for (const width of [390, 768]) {
    await s.operator.setViewportSize({ width, height: 844 });
    expect(await s.operator.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(s.operator.getByRole('button', { name: 'Iniciar recorrido', exact: true })).toBeVisible();
  }
  await s.operator.screenshot({ path: 'artifacts/phase5/operador-tablet.png', fullPage: true });
  await tv.close();
  expect(s.errors).toEqual([]);
});
