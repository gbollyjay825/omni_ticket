(function () {
  'use strict'

  document.documentElement.dataset.omniWidgetLoader = 'loading'
  if (window.OmniWidget) return

  var script = document.currentScript
  if (!script) {
    script = Array.prototype.find.call(document.scripts, function (candidate) {
      return /\/omni-widget\.js(?:\?|$)/.test(candidate.src || '')
    })
  }
  if (!script || !script.src) return
  var scriptUrl = new URL(script.src, window.location.href)
  var baseUrl = (script.dataset.baseUrl || scriptUrl.origin).replace(/\/$/, '')
  var apiUrl = (script.dataset.apiUrl || baseUrl).replace(/\/$/, '')
  var market = (script.dataset.market || 'ng').trim().toLowerCase()
  var root = null
  var frame = null
  var launcher = null
  var autoOpenTimer = null

  function setOpen(open) {
    if (!frame || !launcher) return
    frame.hidden = !open
    launcher.hidden = open
    launcher.setAttribute('aria-expanded', open ? 'true' : 'false')
  }

  function destroy() {
    if (autoOpenTimer) window.clearTimeout(autoOpenTimer)
    window.removeEventListener('message', receiveMessage)
    if (root) root.remove()
    root = null
    frame = null
    launcher = null
    delete window.OmniWidget
  }

  function receiveMessage(event) {
    if (!frame || event.source !== frame.contentWindow) return
    if (event.origin !== new URL(baseUrl).origin) return
    if (event.data && event.data.type === 'omni-widget:close') setOpen(false)
  }

  function mount(config) {
    if (!config.enabled || root) {
      document.documentElement.dataset.omniWidgetLoader = config.enabled ? 'ready' : 'disabled'
      return
    }
    root = document.createElement('div')
    root.id = 'omni-widget-root'
    root.dataset.position = config.position || 'bottom-right'

    frame = document.createElement('iframe')
    frame.className = 'omni-widget-frame'
    frame.title = config.display_name || 'Omni support messenger'
    frame.src = baseUrl + '/?screen=widget&market=' + encodeURIComponent(market)
    frame.allow = 'clipboard-write'
    frame.hidden = true

    launcher = document.createElement('button')
    launcher.className = 'omni-widget-launcher'
    launcher.type = 'button'
    launcher.setAttribute('aria-label', config.launcher_label || 'Open support messenger')
    launcher.setAttribute('aria-expanded', 'false')
    launcher.style.backgroundColor = config.primary_color || '#0b5eea'
    launcher.innerHTML =
      '<span class="omni-widget-bubble" aria-hidden="true"></span>' +
      '<span class="omni-widget-label"></span>'
    launcher.querySelector('.omni-widget-label').textContent = config.launcher_label || 'Support'
    launcher.addEventListener('click', function () {
      setOpen(frame.hidden)
    })

    var style = document.createElement('style')
    style.textContent =
      '#omni-widget-root{position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}' +
      '#omni-widget-root[data-position="bottom-left"]{right:auto;left:20px}' +
      '.omni-widget-frame{display:block;width:min(376px,calc(100vw - 28px));height:min(620px,calc(100dvh - 96px));margin-bottom:12px;background:#fff;border:0;border-radius:8px;box-shadow:0 18px 50px rgba(25,48,68,.24)}' +
      '.omni-widget-frame[hidden]{display:none}' +
      '.omni-widget-launcher{display:flex;align-items:center;justify-content:center;gap:9px;min-height:48px;margin-left:auto;padding:0 16px;color:#fff;border:0;border-radius:24px;box-shadow:0 10px 28px rgba(25,48,68,.28);cursor:pointer;font:700 14px/1 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}' +
      '.omni-widget-launcher[hidden]{display:none}' +
      '#omni-widget-root[data-position="bottom-left"] .omni-widget-launcher{margin-left:0;margin-right:auto}' +
      '.omni-widget-bubble{position:relative;width:18px;height:15px;border:2px solid currentColor;border-radius:5px}' +
      '.omni-widget-bubble:after{content:"";position:absolute;left:2px;bottom:-5px;width:5px;height:5px;border-left:2px solid currentColor;transform:skewY(-35deg)}' +
      '@media(max-width:480px){#omni-widget-root,#omni-widget-root[data-position="bottom-left"]{right:0;bottom:0;left:0}.omni-widget-frame{width:100vw;height:100dvh;margin:0;border-radius:0}.omni-widget-launcher{margin:0 14px 14px auto}#omni-widget-root[data-position="bottom-left"] .omni-widget-launcher{margin:0 auto 14px 14px}}'

    root.appendChild(style)
    root.appendChild(frame)
    root.appendChild(launcher)
    document.body.appendChild(root)
    document.documentElement.dataset.omniWidgetLoader = 'ready'
    window.addEventListener('message', receiveMessage)

    var delay = Number(config.auto_open_seconds || 0)
    if (delay > 0) autoOpenTimer = window.setTimeout(function () { setOpen(true) }, delay * 1000)
  }

  window.OmniWidget = {
    open: function () { setOpen(true) },
    close: function () { setOpen(false) },
    destroy: destroy,
  }

  fetch(apiUrl + '/api/v1/widget/' + encodeURIComponent(market) + '/config', {
    credentials: 'omit',
    headers: { Accept: 'application/json' },
  })
    .then(function (response) {
      if (!response.ok) throw new Error('Messenger configuration unavailable')
      return response.json()
    })
    .then(mount)
    .catch(function () {
      document.documentElement.dataset.omniWidgetLoader = 'unavailable'
      // A missing or disabled public configuration must leave the host page unchanged.
    })
})()
