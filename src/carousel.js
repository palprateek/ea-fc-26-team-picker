export function createCarousel(pool) {
  const DURATION = 3500;

  return {
    spin() {
      const teamIndex = Math.floor(Math.random() * pool.length);
      const team = pool[teamIndex];

      return {
        team,
        pool,
        duration: DURATION,
      };
    },
  };
}
