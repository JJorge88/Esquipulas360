import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = () => JSON.parse(readFileSync('artifacts/editor-session.json', 'utf8'));
const url = id => `/admin/tours/scene/${id}/editor/`;
const openEditor = async (page, name) => {
  const data = fixture().scenes[name];
  await page.goto(url(data.a));
  await expect(page.locator('#main')).toHaveAttribute('data-loading', 'false');
  return data;
};
const at = async (page, x = .5, y = .4) => {
  const b = await page.locator('#editor-scene canvas').boundingBox();
  return { x: b.x + b.width * x, y: b.y + b.height * y };
};
const clickPanorama = async (page, x = .5, y = .4) => { const p = await at(page, x, y); await page.mouse.click(p.x, p.y); };
const drag = async page => {
  const from = await at(page, .75, .4), to = await at(page, .4, .6);
  await page.mouse.move(from.x, from.y); await page.mouse.down(); await page.mouse.move(to.x, to.y, { steps: 12 }); await page.mouse.up();
};
const savedData = async (page, id) => (await page.request.get(url(id) + 'data/')).json();
const addDraft = async (page, destination, label = 'Nuevo punto visual') => {
  await page.getByRole('button', { name: 'Añadir punto', exact: true }).click();
  await clickPanorama(page, .6, .4);
  await page.getByLabel('Etiqueta', { exact: true }).fill(label);
  await page.getByLabel('Escena de destino', { exact: true }).selectOption(String(destination));
};

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: 'sessionid', value: fixture().cookie, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' }]);
});

test('visual creation, editing, relocation, persistence, marker selection and confirmed deletion', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const f = await openEditor(page, 'flow');
  await addDraft(page, f.b);
  await expect(page.locator('[data-point="new"]')).toHaveCount(1);
  await expect(page.locator('#main')).toHaveAttribute('data-dirty', 'true');
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toHaveText('Punto guardado.');
  const point = (await savedData(page, f.a)).points.find(p => p.label === 'Nuevo punto visual');
  expect(point.yaw).toBeLessThan(0); expect(point.pitch).toBeGreaterThan(0);
  await page.reload(); await expect(page.locator('#main')).toHaveAttribute('data-loading', 'false');
  const marker = page.locator(`[data-point="${point.id}"]`);
  await expect(marker).toHaveAttribute('data-yaw', String(point.yaw));
  const hit = await marker.evaluate(el => {
    const point = new AFRAME.THREE.Vector3(); el.object3D.getWorldPosition(point); point.project(el.sceneEl.camera);
    const b = el.sceneEl.canvas.getBoundingClientRect(); return { x: b.x + (point.x + 1) / 2 * b.width, y: b.y + (1 - point.y) / 2 * b.height };
  });
  await page.mouse.click(hit.x, hit.y);
  await expect(page.getByLabel('Etiqueta', { exact: true })).toHaveValue('Nuevo punto visual');
  expect(page.url()).toContain(url(f.a));
  await page.getByLabel('Etiqueta', { exact: true }).fill('Punto reubicado');
  await page.getByRole('button', { name: 'Cambiar posición' }).click();
  await clickPanorama(page, .25, .65);
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toHaveText('Punto guardado.');
  const changed = (await savedData(page, f.a)).points.find(p => p.id === point.id);
  expect(changed.label).toBe('Punto reubicado'); expect(changed.yaw).toBeGreaterThan(0); expect(changed.pitch).toBeLessThan(0);
  await page.screenshot({ path: 'artifacts/editor-desktop.png', fullPage: true });
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Eliminar punto', exact: true }).click();
  expect((await savedData(page, f.a)).points.some(p => p.id === point.id)).toBe(true);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Eliminar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toHaveText('Punto eliminado.');
  expect((await savedData(page, f.a)).points.some(p => p.id === point.id)).toBe(false);
  expect(errors).toEqual([]);
});

test('dragging and ordinary clicks never create points without an explicit placement click', async ({ page }) => {
  const f = await openEditor(page, 'drag');
  await clickPanorama(page, .8, .3);
  await expect(page.locator('[data-point="new"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Añadir punto', exact: true }).click();
  await drag(page);
  await expect(page.locator('#main')).toHaveAttribute('data-placement', 'true');
  await expect(page.locator('[data-point="new"]')).toHaveCount(0);
  expect((await savedData(page, f.a)).points).toHaveLength(1);
  await clickPanorama(page);
  await expect(page.locator('[data-point="new"]')).toHaveCount(1);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await expect(page.locator('#main')).toHaveAttribute('data-dirty', 'false');
  await expect(page.locator('[data-point="new"]')).toHaveCount(0);
});

test('failed and unconfirmed saves keep draft values and retry avoids duplicate creation', async ({ page }) => {
  const f = await openEditor(page, 'failure');
  await addDraft(page, f.b, 'Conservar mi edición');
  const endpoint = '**' + url(f.a) + 'points/';
  await page.route(endpoint, route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Error temporal de prueba.' }) }));
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toContainText('Tus cambios siguen en pantalla');
  await expect(page.getByLabel('Etiqueta', { exact: true })).toHaveValue('Conservar mi edición');
  await expect(page.locator('#main')).toHaveAttribute('data-dirty', 'true');
  await page.unroute(endpoint);
  // Server commits but response is lost: the same draft key must be reusable.
  await page.route(endpoint, async route => { await route.fetch(); await route.abort(); });
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toContainText('Tus cambios siguen en pantalla');
  expect((await savedData(page, f.a)).points).toHaveLength(2);
  await page.unroute(endpoint);
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toHaveText('Punto guardado.');
  expect((await savedData(page, f.a)).points).toHaveLength(2);
  await expect(page.locator('#main')).toHaveAttribute('data-dirty', 'false');
});

test('initial orientation saves the direction being viewed and private preview uses the same camera', async ({ page }) => {
  const f = await openEditor(page, 'orientation');
  await drag(page);
  const before = await page.evaluate(() => PanoramaTools.currentOrientation(document.querySelector('#editor-scene')));
  await page.getByRole('button', { name: 'Usar esta vista al iniciar' }).click();
  await page.getByRole('button', { name: 'Guardar orientación', exact: true }).click();
  await expect(page.locator('#editor-feedback')).toHaveText('Orientación inicial guardada.');
  const data = await savedData(page, f.a);
  expect(data.scene.orientation.yaw).toBeCloseTo(before.yaw, 2); expect(data.scene.orientation.pitch).toBeCloseTo(before.pitch, 2);
  await drag(page);
  await page.getByRole('button', { name: 'Restaurar vista guardada' }).click();
  const restored = await page.evaluate(() => PanoramaTools.currentOrientation(document.querySelector('#editor-scene')));
  expect(restored.yaw).toBeCloseTo(before.yaw, 2); expect(restored.pitch).toBeCloseTo(before.pitch, 2);
  await page.reload(); await expect(page.locator('#main')).toHaveAttribute('data-loading', 'false');
  const reloaded = await page.evaluate(() => PanoramaTools.currentOrientation(document.querySelector('#editor-scene')));
  expect(reloaded.yaw).toBeCloseTo(before.yaw, 2);
  const popupPromise = page.waitForEvent('popup'); await page.getByRole('link', { name: 'Probar datos guardados' }).click(); const preview = await popupPromise;
  await expect(preview.locator('#main')).toHaveAttribute('data-scene', 'azul');
  const privateView = await preview.evaluate(() => PanoramaTools.currentOrientation(document.querySelector('#panorama-scene')));
  expect(privateView.yaw).toBeCloseTo(before.yaw, 2); expect(privateView.pitch).toBeCloseTo(before.pitch, 2);
  await expect(preview.getByText(/PRUEBA PRIVADA/)).toBeVisible();
  await preview.getByRole('combobox', { name: 'Seleccionar escena' }).selectOption('ambar');
  await expect(preview.locator('#main')).toHaveAttribute('data-scene', 'ambar');
  await preview.getByRole('button', { name: 'Volver a azul' }).click();
  await expect(preview.locator('#main')).toHaveAttribute('data-scene', 'azul');
  expect((await page.request.get(`/recorridos/${f.slug}/`)).status()).toBe(404);
  await preview.close();
});

test('pending changes warn on exit and preview sees saved data without discarding local edits', async ({ page }) => {
  const f = await openEditor(page, 'pending');
  await addDraft(page, f.b, 'Todavía sin guardar');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('link', { name: 'Volver al admin' }).click();
  expect(page.url()).toContain(url(f.a));
  const popupPromise = page.waitForEvent('popup'); await page.getByRole('link', { name: 'Probar datos guardados' }).click(); const preview = await popupPromise;
  await expect(page.locator('#editor-feedback')).toContainText('Hay cambios pendientes');
  await expect(preview.locator('#main')).toHaveAttribute('data-scene', 'azul');
  expect(JSON.parse(await preview.locator('#tour-data').textContent()).scenes[0].hotspots).toHaveLength(1);
  await expect(page.getByLabel('Etiqueta', { exact: true })).toHaveValue('Todavía sin guardar');
  await preview.close();
  const dialogPromise = page.waitForEvent('dialog');
  await page.evaluate(() => { setTimeout(() => location.reload(), 0); });
  const dialog = await dialogPromise; expect(dialog.type()).toBe('beforeunload'); await dialog.dismiss();
  await expect(page.getByLabel('Etiqueta', { exact: true })).toHaveValue('Todavía sin guardar');
});

test('marker position matches public viewer and navigation remains active only in viewer', async ({ page }) => {
  const f = fixture().demo;
  await page.goto(url(f.a)); await expect(page.locator('#main')).toHaveAttribute('data-loading', 'false');
  await page.locator('#point-list button').first().click();
  await page.getByRole('button', { name: 'Cambiar posición' }).click(); await clickPanorama(page, .57, .42);
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click(); await expect(page.locator('#editor-feedback')).toHaveText('Punto guardado.');
  const position = await page.locator('#editor-markers [data-point]').first().evaluate(el => el.object3D.position.toArray());
  await page.goto('/recorridos/demostracion/'); await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
  const actual = await page.locator('#hotspots [data-hotspot]').first().evaluate(el => el.object3D.position.toArray());
  actual.forEach((n, i) => expect(n).toBeCloseTo(position[i], 8));
  const hit = await page.locator('#hotspots [data-hotspot]').first().evaluate(el => {
    const point = new AFRAME.THREE.Vector3(); el.object3D.getWorldPosition(point); point.project(el.sceneEl.camera);
    const b = el.sceneEl.canvas.getBoundingClientRect(); return { x: b.x + (point.x + 1) / 2 * b.width, y: b.y + (1 - point.y) / 2 * b.height };
  });
  await page.mouse.click(hit.x, hit.y); await expect(page.locator('#main')).toHaveAttribute('data-scene', 'ambar');
  await page.getByRole('button', { name: 'Volver a escena azul' }).click(); await expect(page.locator('#main')).toHaveAttribute('data-scene', 'azul');
});

test('mobile layout and touch dragging allow deliberate point placement', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await context.addCookies([{ name: 'sessionid', value: fixture().cookie, domain: '127.0.0.1', path: '/' }]);
  const page = await context.newPage(), f = fixture().scenes.mobile;
  await page.goto('http://127.0.0.1:8013' + url(f.a)); await expect(page.locator('#main')).toHaveAttribute('data-loading', 'false');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Añadir punto', exact: true }).click();
  await page.locator('#editor-scene canvas').scrollIntoViewIfNeeded();
  const from = await at(page, .8, .4), to = await at(page, .3, .6), session = await context.newCDPSession(page);
  await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [from] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [to] });
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await expect(page.locator('[data-point="new"]')).toHaveCount(0);
  const orientation = await page.evaluate(() => PanoramaTools.currentOrientation(document.querySelector('#editor-scene')));
  expect(Math.abs(orientation.yaw)).toBeGreaterThan(5); expect(Math.abs(orientation.pitch)).toBeGreaterThan(5);
  const tap = await at(page, .5, .4); await page.touchscreen.tap(tap.x, tap.y);
  await expect(page.locator('[data-point="new"]')).toHaveCount(1);
  await page.getByLabel('Etiqueta', { exact: true }).fill('Punto móvil');
  await page.getByLabel('Escena de destino', { exact: true }).selectOption(String(f.b));
  await page.getByRole('button', { name: 'Guardar punto', exact: true }).click(); await expect(page.locator('#editor-feedback')).toHaveText('Punto guardado.');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/editor-mobile.png', fullPage: true });
  await context.close();
});
