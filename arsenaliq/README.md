# ArsenalIQ
Pitcher-evaluation web app built around arsenal quality, underlying performance, projection and development opportunity.

## Build the live 2026 database
Requires Python 3.10+ and pandas.

```bash
pip install pandas
python scripts/build_data.py --year 2026 --min-pitches 50
python -m http.server 8000
```
Open `http://localhost:8000`.

The builder pulls public Baseball Savant leaderboards for pitch outcomes, velocity, movement, expected statistics and arm angle, joins by MLBAM player ID, computes transparent 20–80 ArsenalIQ pitch grades, and writes `data/pitchers.json`. Re-run the script to refresh the database.

## Model notes
- Pitch grades are normalized within pitch type from whiff%, RV/100, xwOBA and hard-hit rate.
- Overall Arsenal is usage-weighted.
- Projection currently blends arsenal and expected-performance signal.
- Command is intentionally blank until pitch-level target/location inference is added; strike rate is not the same thing as command.
- Every model-derived grade is labeled ArsenalIQ, not an official MLB/Statcast/FanGraphs grade.
