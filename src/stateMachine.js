const TRANSITIONS = {
  loading:  { modelLoaded: 'waiting' },
  waiting:  { faceDetected: 'ready' },
  ready:    { spinTriggered: 'spinning', faceLost: 'waiting' },
  spinning: { spinCompleted: 'result' },
  result:   { spinAgainTriggered: 'spinning' },
};

export function createStateMachine() {
  let state = 'loading';
  const observers = [];

  return {
    getState() {
      return state;
    },

    dispatch(event) {
      const table = TRANSITIONS[state];
      const next = table?.[event];
      if (!next) return;

      const from = state;
      state = next;
      for (const fn of observers) {
        fn({ from, to: next, event });
      }
    },

    onTransition(fn) {
      observers.push(fn);
    },
  };
}
