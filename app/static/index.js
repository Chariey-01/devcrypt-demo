(function () {
  var clockEl = document.getElementById('landing-clock');
  function tick() {
    clockEl.textContent = new Date().toLocaleTimeString([], { hour12: false });
  }
  tick();
  setInterval(tick, 1000);

  fetch('/leaderboard/data')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      document.getElementById('landing-team-count').textContent = (data.leaderboard || []).length;
    })
    .catch(function () {
      document.getElementById('landing-team-count').textContent = '0';
    });
})();
