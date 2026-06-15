export function createTeamData(teams) {
  const leagues = [];
  const seenLeagues = new Set();
  for (const t of teams) {
    if (t.leagueId != null && !seenLeagues.has(t.leagueId)) {
      seenLeagues.add(t.leagueId);
      leagues.push({ id: t.leagueId, name: t.leagueName });
    }
  }

  const countries = [];
  const seenCountries = new Set();
  for (const t of teams) {
    const c = t.country;
    if (c && !seenCountries.has(c)) {
      seenCountries.add(c);
      countries.push(c);
    }
  }
  countries.sort();

  return {
    getAll() {
      return teams;
    },

    getByLeague(leagueId) {
      return teams.filter(t => t.leagueId === leagueId);
    },

    getByCountry(country) {
      return teams.filter(t => t.country === country);
    },

    getFiltered(leagueId, country) {
      return teams.filter(t => {
        if (leagueId != null && t.leagueId !== leagueId) return false;
        if (country && t.country !== country) return false;
        return true;
      });
    },

    countFiltered(leagueId, country) {
      let n = 0;
      for (const t of teams) {
        if (leagueId != null && t.leagueId !== leagueId) continue;
        if (country && t.country !== country) continue;
        n++;
      }
      return n;
    },

    getLeagues() {
      return leagues;
    },

    getCountries() {
      return countries;
    },
  };
}
