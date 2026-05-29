/* Widget flutuante do assistente de IA — consome SSE do backend. */
(function () {
  'use strict';
  var launcher = document.getElementById('cw-launcher');
  var win = document.getElementById('cw-window');
  if (!launcher || !win) return;

  var body = document.getElementById('cw-body');
  var texto = document.getElementById('cw-texto');
  var btnSend = document.getElementById('cw-send');
  var btnNova = document.getElementById('cw-nova');
  var btnFechar = document.getElementById('cw-fechar');
  var carregado = false;
  var enviando = false;

  function rolar() { body.scrollTop = body.scrollHeight; }

  function bolha(classe, texto) {
    var d = document.createElement('div');
    d.className = 'cw-bolha ' + classe;
    d.textContent = texto || '';
    body.appendChild(d);
    rolar();
    return d;
  }

  function vazio() {
    body.innerHTML = '<div class="cw-vazio">Pergunte algo como<br>' +
      '<em>"quantos pacientes eu tenho?"</em><br>ou <em>"resuma a anamnese do paciente João"</em>.</div>';
  }

  function carregarHistorico() {
    fetch(window.CW_URLS.historico, { headers: { 'X-CSRFToken': window.CW_CSRF } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        body.innerHTML = '';
        if (!d.mensagens || !d.mensagens.length) { vazio(); return; }
        d.mensagens.forEach(function (m) {
          bolha(m.papel === 'user' ? 'cw-user' : 'cw-assistant', m.conteudo);
        });
      })
      .catch(function () { vazio(); });
  }

  function abrir() {
    win.classList.add('cw-open');
    localStorage.setItem('cw_open', '1');
    if (!carregado) { carregarHistorico(); carregado = true; }
    texto.focus();
  }
  function fechar() {
    win.classList.remove('cw-open');
    localStorage.setItem('cw_open', '0');
  }

  launcher.addEventListener('click', function () {
    win.classList.contains('cw-open') ? fechar() : abrir();
  });
  btnFechar.addEventListener('click', fechar);

  btnNova.addEventListener('click', function () {
    fetch(window.CW_URLS.nova, { method: 'POST', headers: { 'X-CSRFToken': window.CW_CSRF } })
      .then(function () { vazio(); });
  });

  function enviar() {
    var msg = texto.value.trim();
    if (!msg || enviando) return;
    if (body.querySelector('.cw-vazio')) body.innerHTML = '';
    enviando = true;
    btnSend.disabled = true;
    texto.value = '';
    bolha('cw-user', msg);

    var statusEl = bolha('cw-status', 'Pensando…');
    var assistantEl = null;

    var fd = new FormData();
    fd.append('texto', msg);
    fd.append('csrf_token', window.CW_CSRF);

    fetch(window.CW_URLS.mensagem, {
      method: 'POST', body: fd, headers: { 'X-CSRFToken': window.CW_CSRF }
    }).then(function (resp) {
      if (!resp.ok && resp.status !== 200) {
        return resp.json().then(function (j) { throw new Error(j.erro || 'Erro'); });
      }
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function processar(texto) {
        buffer += texto;
        var partes = buffer.split('\n\n');
        buffer = partes.pop();
        partes.forEach(function (bloco) {
          var linha = bloco.split('\n').find(function (l) { return l.indexOf('data:') === 0; });
          if (!linha) return;
          var ev;
          try { ev = JSON.parse(linha.slice(5).trim()); } catch (e) { return; }
          if (ev.tipo === 'status') {
            statusEl.textContent = '🔍 consultando: ' + ev.tool;
          } else if (ev.tipo === 'token') {
            if (!assistantEl) { statusEl.remove(); assistantEl = bolha('cw-assistant', ''); }
            assistantEl.textContent += ev.texto;
            rolar();
          } else if (ev.tipo === 'erro') {
            if (statusEl.parentNode) statusEl.remove();
            bolha('cw-assistant cw-erro', ev.texto);
          }
        });
      }

      function ler() {
        return reader.read().then(function (res) {
          if (res.done) { if (statusEl.parentNode) statusEl.remove(); return; }
          processar(decoder.decode(res.value, { stream: true }));
          return ler();
        });
      }
      return ler();
    }).catch(function (e) {
      if (statusEl.parentNode) statusEl.remove();
      bolha('cw-assistant cw-erro', e.message || 'Falha de conexão.');
    }).finally(function () {
      enviando = false;
      btnSend.disabled = false;
      texto.focus();
    });
  }

  btnSend.addEventListener('click', enviar);
  texto.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
  });

  // Restaura estado aberto/fechado entre navegações
  if (localStorage.getItem('cw_open') === '1') abrir();
})();
