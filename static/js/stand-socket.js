/* Same-origin WebSockets; role credentials are HttpOnly cookies, never URL/query tokens. */
(() => {
  class StandSocket {
    constructor(config, receive, status) {
      this.config = config; this.receive = receive; this.status = status;
      this.stopped = false; this.attempt = 0; this.lastMessage = 0;
      this.timer = setInterval(() => {
        if (this.socket?.readyState === WebSocket.OPEN) {
          this.send({ type: 'ping' });
          if (Date.now() - this.lastMessage > 6500) { this.status(false, 'Conexión interrumpida. Recuperando el estado…'); this.socket.close(); }
        }
      }, 2000);
      window.addEventListener('pagehide', () => { this.stopped = true; clearTimeout(this.retry); this.socket?.close(); });
      window.addEventListener('pageshow', event => { if (event.persisted) { this.stopped = false; this.connect(); } });
      this.connect();
    }
    connect() {
      if (this.stopped) return;
      const url = new URL(this.config.socket, location.origin); url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = this.socket = new WebSocket(url);
      socket.onopen = () => { this.lastMessage = Date.now(); this.send({ type: 'ping' }); };
      socket.onmessage = event => {
        if (socket !== this.socket) return;
        this.lastMessage = Date.now(); this.attempt = 0;
        let data; try { data = JSON.parse(event.data); } catch { return; }
        if (data.type === 'state') { this.status(true, 'Conectado al stand'); this.receive(data); }
        else if (!['pong', 'heartbeat'].includes(data.type)) this.receive(data);
      };
      socket.onclose = async event => {
        if (this.stopped || socket !== this.socket) return;
        if ([4401, 4403, 4409, 4429].includes(event.code)) {
          this.stopped = true;
          const message = event.code === 4409 ? 'Ya hay otra ventana de este dispositivo conectada. Ciérrala y recarga esta página.' : event.code === 4429 ? 'Se enviaron demasiados mensajes. Recarga para reconectar.' : 'La sesión terminó o el acceso dejó de ser válido.';
          this.status(false, message);
          if (event.code !== 4409 && event.code !== 4429) this.receive({ type: 'ended' });
          return;
        }
        this.status(false, 'Sin conexión. Conservamos la escena y estamos reconectando…');
        this.retry = setTimeout(() => this.connect(), Math.min(5000, 700 * 2 ** this.attempt++) + Math.random() * 300);
      };
      socket.onerror = () => this.status(false, 'No hay conexión con la sincronización. Comprueba el servidor y la red.');
    }
    send(data) {
      if (this.socket?.readyState !== WebSocket.OPEN || this.socket.bufferedAmount > 16384) return false;
      this.socket.send(JSON.stringify(data)); return true;
    }
  }
  window.StandSocket = StandSocket;
})();
