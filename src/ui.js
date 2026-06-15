export function createUI(elements, teamData, callbacks) {
  const { leagueRow, countryRow, spinBtn, spinAgainBtn, prompt, loadingScreen, faceBadge, faceBadgeText, statusStrip, viewfinderCorners, leagueBar } = elements;
  let activeLeague = null;
  let activeCountry = null;
  let faceCount = 0;
  let currentState = 'loading';
  let activePoolSize = 0;

  function renderLeagueChips() {
    const leagues = teamData.getLeagues();
    leagueRow.innerHTML = '';

    const allChip = createChip('All Leagues', null, activeLeague === null, teamData.countFiltered(null, activeCountry));
    allChip.addEventListener('click', () => selectLeague(null));
    leagueRow.appendChild(allChip);

    for (const league of leagues) {
      const count = teamData.countFiltered(league.id, activeCountry);
      const chip = createChip(league.name, league.id, activeLeague === league.id, count);
      chip.addEventListener('click', () => selectLeague(league.id));
      leagueRow.appendChild(chip);
    }
  }

  function renderCountryChips() {
    if (!countryRow) return;
    const countries = teamData.getCountries();
    countryRow.innerHTML = '';

    const allChip = createChip('All Countries', null, activeCountry === null, teamData.countFiltered(activeLeague, null));
    allChip.addEventListener('click', () => selectCountry(null));
    countryRow.appendChild(allChip);

    for (const country of countries) {
      const label = country.charAt(0).toUpperCase() + country.slice(1).replace(/-/g, ' ');
      const count = teamData.countFiltered(activeLeague, country);
      const chip = createChip(label, country, activeCountry === country, count);
      chip.addEventListener('click', () => selectCountry(country));
      countryRow.appendChild(chip);
    }
  }

  function createChip(label, value, isActive, matchCount) {
    const chip = document.createElement('button');
    const incompatible = matchCount === 0;
    chip.className = 'league-chip'
      + (isActive ? ' active' : '')
      + (incompatible ? ' incompatible' : '');
    chip.textContent = label;
    chip.dataset.value = value || '';
    if (incompatible) {
      chip.disabled = true;
      chip.title = 'No teams match this combination';
    }
    return chip;
  }

  function selectLeague(leagueId) {
    activeLeague = leagueId;
    renderLeagueChips();
    callbacks.onFilterChange(activeLeague, activeCountry);
  }

  function selectCountry(country) {
    activeCountry = country;
    renderCountryChips();
    callbacks.onFilterChange(activeLeague, activeCountry);
  }

  function refreshStatus() {
    if (!statusStrip) return;
    const label = statusStrip.querySelector('.status-label');
    if (!label) return;

    let phase;
    if (currentState === 'loading') phase = 'MATCHDAY · LOADING';
    else if (currentState === 'waiting') phase = 'MATCHDAY · IDLE';
    else if (currentState === 'ready') phase = 'MATCHDAY · ARMED';
    else if (currentState === 'spinning') phase = 'MATCHDAY · SAMPLING';
    else if (currentState === 'result') phase = 'MATCHDAY · FINAL';
    else phase = 'MATCHDAY';

    const facePart = currentState === 'loading'
      ? ''
      : `<span style="opacity:0.55">·</span> FACES · ${faceCount}`;

    label.innerHTML = `<span class="pulse-dot"></span>${phase} ${facePart}`;
  }

  function setFaceCount(n) {
    if (n !== faceCount) {
      faceCount = n;
      refreshStatus();
    }
    if (faceBadge) {
      faceBadge.classList.toggle('active', n > 0);
    }
    if (faceBadgeText) {
      faceBadgeText.textContent = `FACES · ${n}`;
    }
  }

  function setPoolSize(n) {
    if (n === activePoolSize) return;
    activePoolSize = n;
    const app = document.getElementById('app');
    app.classList.toggle('empty-pool', n === 0);
    if (spinBtn && currentState === 'ready') {
      spinBtn.disabled = n === 0;
      const label = spinBtn.querySelector('.spin-label');
      const sub = spinBtn.querySelector('.spin-sub');
      if (n === 0) {
        if (label) label.textContent = 'NO TEAMS';
        if (sub) sub.textContent = 'ADJUST FILTERS';
      } else {
        if (label) label.textContent = 'SPIN';
        if (sub) sub.textContent = 'TAP TO ASSIGN CLUB';
      }
    }
  }

  function setState(appState) {
    const app = document.getElementById('app');
    app.classList.remove('loading', 'waiting', 'ready', 'spinning', 'result');
    app.classList.add(appState);
    currentState = appState;

    prompt.classList.toggle('visible', appState === 'waiting');

    if (appState === 'ready') {
      spinBtn.disabled = activePoolSize === 0;
      spinBtn.classList.toggle('ready', activePoolSize > 0);
      const label = spinBtn.querySelector('.spin-label');
      const sub = spinBtn.querySelector('.spin-sub');
      if (activePoolSize === 0) {
        if (label) label.textContent = 'NO TEAMS';
        if (sub) sub.textContent = 'ADJUST FILTERS';
      } else {
        if (label) label.textContent = 'SPIN';
        if (sub) sub.textContent = 'TAP TO ASSIGN CLUB';
      }
    } else {
      spinBtn.disabled = true;
      spinBtn.classList.remove('ready');
    }
    spinBtn.style.display = (appState === 'result' || appState === 'spinning') ? 'none' : '';
    spinAgainBtn.style.display = appState === 'result' ? '' : 'none';

    loadingScreen.classList.toggle('hidden', appState !== 'loading');

    if (appState === 'ready' || appState === 'result' || appState === 'spinning') {
      app.classList.add('camera-active');
    }

    if (faceBadge) {
      faceBadge.classList.toggle('active', faceCount > 0);
    }
    if (faceBadgeText) {
      faceBadgeText.textContent = `FACES · ${faceCount}`;
    }

    if (statusStrip) {
      const faded = appState === 'spinning' || appState === 'result';
      statusStrip.classList.toggle('faded', faded);
    }
    if (viewfinderCorners) {
      viewfinderCorners.classList.toggle('faded', appState === 'spinning');
    }
    if (leagueBar) {
      leagueBar.classList.toggle('faded', appState === 'spinning');
    }

    refreshStatus();
  }

  renderLeagueChips();
  renderCountryChips();

  spinBtn.addEventListener('click', () => {
    if (activePoolSize === 0) return;
    callbacks.onSpin();
  });
  spinAgainBtn.addEventListener('click', () => {
    if (activePoolSize === 0) return;
    callbacks.onSpinAgain();
  });

  return {
    setState,
    setFaceCount,
    setPoolSize,
    getActiveLeague() { return activeLeague; },
    getActiveCountry() { return activeCountry; },
  };
}
