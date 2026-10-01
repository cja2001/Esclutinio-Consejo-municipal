// Mide el espacio disponible para el mapa y si la pantalla es de teléfono. El servidor lo usa
// para encuadrar el mapa y acomodar los gráficos. Dash carga este archivo solo.
(function () {
  function medir() {
    var c = document.getElementById("card-mapa");
    var w = 680;
    if (c && c.clientWidth) {
      var s = getComputedStyle(c);
      w = c.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
    }
    var m = { w: Math.round(w), movil: window.innerWidth < 600 };
    m.clave = Math.round(m.w / 40) + "-" + m.movil;
    return m;
  }

  var ultimo = null, espera = null;

  window.dash_clientside = Object.assign({}, window.dash_clientside, {
    pantalla: { medir: function () { var m = medir(); ultimo = m.clave; return m; } },
  });

  // Al girar el teléfono o cambiar el tamaño de la ventana se vuelve a medir. Solo cuenta el ancho:
  // en el teléfono el alto cambia cada vez que se oculta la barra del navegador al hacer scroll.
  window.addEventListener("resize", function () {
    clearTimeout(espera);
    espera = setTimeout(function () {
      var m = medir();
      if (ultimo !== null && m.clave !== ultimo && window.dash_clientside.set_props) {
        ultimo = m.clave;
        window.dash_clientside.set_props("pantalla", { data: m });
      }
    }, 300);
  });
})();
