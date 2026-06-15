export function createUI(elements, teamData, callbacks) {
  const { leagueRow, countryRow, spinBtn, spinAgainBtn, prompt, loadingScreen, faceBadge, faceBadgeText, statusStrip, viewfinderCorners, leagueBar } = elements;
  let activeLeague = null;
  let activeCountry = null;
  let faceCount = 0;
  let currentState = 'loading';
  let activePoolSize = 0;

  // Cached DOM state — we skip mutations when the new value matches the
  // cached one. This is critical on Android, where every classList/style
  // change on a sibling of the backdrop-blurred chip bar can force a
  // compositor repaint and produce a visible flicker.
  let cachedFaceBadgeActive = null;
  let cachedFaceBadgeText = null;
  let cachedStatusLabelHtml = null;
  let cachedSpinBtnDisabled = null;
  let cachedSpinBtnReady = null;
  let cachedSpinLabelText = null;
  let cachedSpinSubText = null;
  let cachedSpinBtnDisplay = null;
  let cachedSpinAgainDisplay = null;
  let cachedLoadingHidden = null;
  let cachedStatusFaded = null;
  let cachedCornersFaded = null;
  let cachedLeagueFaded = null;
  let hasCameraActivated = false;

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

    const html = `<span class="pulse-dot"></span>${phase} ${facePart}`;
    if (html === cachedStatusLabelHtml) return;
    cachedStatusLabelHtml = html;
    label.innerHTML = html;
  }

  function setFaceCount(n) {
    if (n !== faceCount) {
      faceCount = n;
      refreshStatus();
    }

    const shouldBeActive = n > 0;
    if (faceBadge && shouldBeActive !== cachedFaceBadgeActive) {
      cachedFaceBadgeActive = shouldBeActive;
      faceBadge.classList.toggle('active', shouldBeActive);
    }

    if (faceBadgeText) {
      const text = `FACES · ${n}`;
      if (text !== cachedFaceBadgeText) {
        cachedFaceBadgeText = text;
        faceBadgeText.textContent = text;
      }
    }
  }

  function setPoolSize(n) {
    if (n === activePoolSize) return;
    activePoolSize = n;
    const app = document.getElementById('app');
    const shouldBeEmpty = n === 0;
    if (app.classList.contains('empty-pool') !== shouldBeEmpty) {
      app.classList.toggle('empty-pool', shouldBeEmpty);
    }
    if (spinBtn && currentState === 'ready') {
      const shouldBeDisabled = n === 0;
      if (shouldBeDisabled !== cachedSpinBtnDisabled) {
        cachedSpinBtnDisabled = shouldBeDisabled;
        spinBtn.disabled = shouldBeDisabled;
      }
      const label = spinBtn.querySelector('.spin-label');
      const sub = spinBtn.querySelector('.spin-sub');
      if (n === 0) {
        if (label && label.textContent !== 'NO TEAMS') label.textContent = 'NO TEAMS';
        if (sub && sub.textContent !== 'ADJUST FILTERS') sub.textContent = 'ADJUST FILTERS';
      } else {
        if (label && label.textContent !== 'SPIN') label.textContent = 'SPIN';
        if (sub && sub.textContent !== 'TAP TO ASSIGN CLUB') sub.textContent = 'TAP TO ASSIGN CLUB';
      }
    }
  }

  function setState(appState) {
    if (appState === currentState) return;

    const app = document.getElementById('app');
    app.classList.remove('loading', 'waiting', 'ready', 'spinning', 'result');
    app.classList.add(appState);
    currentState = appState;

    const promptVisible = appState === 'waiting';
    if (prompt.classList.contains('visible') !== promptVisible) {
      prompt.classList.toggle('visible', promptVisible);
    }

    if (appState === 'ready') {
      const shouldBeDisabled = activePoolSize === 0;
      if (shouldBeDisabled !== cachedSpinBtnDisabled) {
        cachedSpinBtnDisabled = shouldBeDisabled;
        spinBtn.disabled = shouldBeDisabled;
      }
      const shouldBeReady = activePoolSize > 0;
      if (shouldBeReady !== cachedSpinBtnReady) {
        cachedSpinBtnReady = shouldBeReady;
        spinBtn.classList.toggle('ready', shouldBeReady);
      }
      const label = spinBtn.querySelector('.spin-label');
      const sub = spinBtn.querySelector('.spin-sub');
      if (activePoolSize === 0) {
        if (label && label.textContent !== 'NO TEAMS') label.textContent = 'NO TEAMS';
        if (sub && sub.textContent !== 'ADJUST FILTERS') sub.textContent = 'ADJUST FILTERS';
      } else {
        if (label && label.textContent !== 'SPIN') label.textContent = 'SPIN';
        if (sub && sub.textContent !== 'TAP TO ASSIGN CLUB') sub.textContent = 'TAP TO ASSIGN CLUB';
      }
    } else {
      if (cachedSpinBtnDisabled !== true) {
        cachedSpinBtnDisabled = true;
        spinBtn.disabled = true;
      }
      if (cachedSpinBtnReady !== false) {
        cachedSpinBtnReady = false;
        spinBtn.classList.remove('ready');
      }
    }

    const spinBtnDisplay = (appState === 'result' || appState === 'spinning') ? 'none' : '';
    if (spinBtnDisplay !== cachedSpinBtnDisplay) {
      cachedSpinBtnDisplay = spinBtnDisplay;
      spinBtn.style.display = spinBtnDisplay;
    }
    const spinAgainDisplay = appState === 'result' ? '' : 'none';
    if (spinAgainDisplay !== cachedSpinAgainDisplay) {
      cachedSpinAgainDisplay = spinAgainDisplay;
      spinAgainBtn.style.display = spinAgainDisplay;
    }

    const loadingHidden = appState !== 'loading';
    if (loadingHidden !== cachedLoadingHidden) {
      cachedLoadingHidden = loadingHidden;
      loadingScreen.classList.toggle('hidden', loadingHidden);
    }

    // One-way transition: once the camera is live, never remove the class.
    // This avoids the compositor tearing down / rebuilding the scanline
    // overlay layer on every state change.
    if (!hasCameraActivated &&
        (appState === 'ready' || appState === 'result' || appState === 'spinning')) {
      hasCameraActivated = true;
      app.classList.add('camera-active');
    }

    // faceBadge state is driven by setFaceCount, not by app state. No-op
    // here to avoid redundant classList writes per state transition.

    if (statusStrip) {
      const faded = appState === 'spinning' || appState === 'result';
      if (faded !== cachedStatusFaded) {
        cachedStatusFaded = faded;
        statusStrip.classList.toggle('faded', faded);
      }
    }
    if (viewfinderCorners) {
      const faded = appState === 'spinning';
      if (faded !== cachedCornersFaded) {
        cachedCornersFaded = faded;
        viewfinderCorners.classList.toggle('faded', faded);
      }
    }
    if (leagueBar) {
      const faded = appState === 'spinning';
      if (faded !== cachedLeagueFaded) {
        cachedLeagueFaded = faded;
        leagueBar.classList.toggle('faded', faded);
      }
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
