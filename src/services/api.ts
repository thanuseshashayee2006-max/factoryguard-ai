import { mockMachines } from '@/data/machines';
import { mockAlerts, type MachineAlert } from '@/data/alerts';
import { mockAnalysis } from '@/data/analysis';
import { mockSensorHistory, type Period } from '@/data/sensors';

export const apiConfig = {
  mode: 'backend' as 'demo' | 'backend',
  baseUrl: 'http://127.0.0.1:8000',
  endpoints: {
    machines: '/api/machines',
    machine: (id: string) => `/api/machines/${encodeURIComponent(id)}`,
    technician: '/api/technician/chat',
    analysis: '/analyze',
    machineFailure: '/predict-machine-failure',
    alerts: '/api/alerts',
  },
};

function getMachine(id: string) {
  const machine = mockMachines.find((m) => m.id === id);

  if (!machine) {
    throw new Error('Machine not found in demo inventory.');
  }

  return machine;
}

export const api = {
  listMachines: () => mockMachines,

  getMachine,

  listAlerts: () => mockAlerts,

  async fetchBackendAlerts(): Promise<MachineAlert[]> {
    const response = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.alerts}`);
    if (!response.ok) throw new Error(`Fetching alerts failed: HTTP ${response.status}`);
    const data = await response.json();
    return data.map((a: MachineAlert) => ({ ...a, source: 'trained-ml' as const }));
  },

  async updateBackendAlert(id: string, status: MachineAlert['status']): Promise<MachineAlert> {
    const response = await fetch(
      `${apiConfig.baseUrl}${apiConfig.endpoints.alerts}/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }
    );
    if (!response.ok) throw new Error(`Updating alert failed: HTTP ${response.status}`);
    return { ...await response.json(), source: 'trained-ml' };
  },

  getHistory: (id: string, period: Period) =>
    mockSensorHistory(getMachine(id), period),

  async analyze(id: string) {
    const machine = getMachine(id);
    const baseDemo = mockAnalysis(machine);

    if (apiConfig.mode === 'backend') {
      try {
        const response = await fetch(
          `${apiConfig.baseUrl}${apiConfig.endpoints.machineFailure}`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              machine_id: machine.id,
              machine_name: machine.name,
              air_temperature: Number((machine.temperature + 273.15).toFixed(2)),
              process_temperature: Number((machine.temperature + 283.15).toFixed(2)),
              rotational_speed: machine.rpm,
              torque: machine.torque,
              tool_wear: machine.wear,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(
            `Machine analysis failed with HTTP ${response.status}`
          );
        }

        const backendData = await response.json();

        const isFailure = backendData.prediction === 1;

        return {
          ...baseDemo,
          severity: isFailure ? 'Critical' : 'Healthy',
          prediction: backendData.prediction,
          failureProbability: Number(backendData.failure_probability),
          predictionSource: 'trained-ml',
          recommendation: isFailure
            ? `The ML model predicted a machine failure. Inspect the machine. Failure probability: ${(Number(backendData.failure_probability) * 100).toFixed(1)}%.`
            : `The ML model did not predict a failure for these readings. Continue monitoring. Failure probability: ${(Number(backendData.failure_probability) * 100).toFixed(1)}%.`,
        };
      } catch (err) {
        console.error(
          'Backend analysis failed; using demo analysis:',
          err
        );
      }
    }

    // Fallback keeps the UI usable if the backend is unavailable.
    await new Promise((resolve) => setTimeout(resolve, 750));

    return baseDemo;
  },
};