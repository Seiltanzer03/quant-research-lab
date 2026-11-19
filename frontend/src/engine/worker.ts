/// <reference lib="webworker" />
import { runResearch, issuePaper } from './research';
import { evaluateScenario } from './scenario';
import type { ScenarioInput, Settings, StoredDataset } from './contracts';

self.onmessage = async (event: MessageEvent<{ id: string; task: 'research' | 'scenario' | 'paper'; source: StoredDataset; settings: Settings; input?: ScenarioInput; minutes?: number }>) => {
  const { id, task, source, settings } = event.data;
  try {
    const result = task === 'research'
      ? await runResearch(source, settings, progress => self.postMessage({ id, type: 'progress', progress }))
      : task === 'scenario' ? evaluateScenario(source, event.data.input!, settings)
        : await issuePaper(source, event.data.minutes!, settings);
    self.postMessage({ id, type: 'result', result });
  } catch (error) { self.postMessage({ id, type: 'error', error: error instanceof Error ? error.message : String(error) }); }
};
