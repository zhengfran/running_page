#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const activities = JSON.parse(await readFile(join(root, 'src', 'static', 'activities.json'), 'utf8'));

if (!Array.isArray(activities) || !activities.length) {
  throw new Error('src/static/activities.json must contain at least one public activity');
}

let distanceMeters = 0;
const years = new Set();
for (const activity of activities) {
  if (!Number.isFinite(activity.distance) || !/^\d{4}-/.test(activity.start_date_local || '')) {
    throw new Error(`invalid public activity ${activity.run_id ?? '(unknown id)'}`);
  }
  distanceMeters += activity.distance;
  years.add(Number(activity.start_date_local.slice(0, 4)));
}

const sortedYears = [...years].sort((a, b) => a - b);
const summary = {
  version: 1,
  activityCount: activities.length,
  distanceKmRounded: Math.round(distanceMeters / 1000 / 10) * 10,
  firstYear: sortedYears[0],
  lastYear: sortedYears.at(-1),
};

await writeFile(join(root, 'public', 'running-summary.v1.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log(`wrote running-summary.v1.json (${summary.activityCount} activities · ${summary.distanceKmRounded} km rounded)`);
