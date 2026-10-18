import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import {
  ScanLine,
  RefreshCw,
  TriangleAlert,
  ListChecks,
  ChevronRight,
  MessageSquare,
} from 'lucide-react';

import { api } from '@/services/api';
import { mockAnalysis } from '@/data/analysis';
import { Button } from '@/components/ui/button';
import {
  DemoBadge,
  MachineSelect,
  Status,
  PageHeading,
} from '@/components/factoryguard/shared';
import {
  useTemperature,
  formatTimestamp,
} from '@/components/factoryguard/state';

type AnalysisResult = ReturnType<typeof mockAnalysis> & {
  recommendation?: string;
  prediction?: number;
  failureProbability?: number;
  predictionSource?: string;
};

export function AnalysisPage({ machineId }: { machineId: string }) {
  const navigate = useNavigate();
  const machine = api.getMachine(machineId);
  const [analysis, setAnalysis] = useState<AnalysisResult>(
    () => mockAnalysis(machine)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const temp = useTemperature();

  async function run() {
    setLoading(true);
    setError('');
    setNotice('');

    try {
      const result = (await api.analyze(machineId)) as AnalysisResult;
      setAnalysis(result);

      if (result.recommendation?.includes('ML model')) {
        setNotice(
          'Trained ML model prediction received. Machine readings are simulated; other diagnostics may still contain demo data.'
        );
      } else if (result.recommendation) {
        setNotice(
          'Backend recommendation received. Other diagnostics may still contain demo data.'
        );
      } else {
        setNotice(
          'Demo analysis displayed. No backend recommendation was received.'
        );
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Analysis could not be loaded.'
      );
    } finally {
      setLoading(false);
    }
  }

  const isMLResult = Boolean(analysis.recommendation?.includes('ML model'));
  const isBackendResult = Boolean(analysis.recommendation);

  return (
    <>
      <PageHeading
        title="AI Failure Analysis"
        description="Inspect sensor patterns and review maintenance recommendations."
      >
        <DemoBadge />
      </PageHeading>

      <div className="analysis-toolbar">
        <div>
          <label>Machine context</label>
          <MachineSelect
            value={machineId}
            onChange={(machine) =>
              navigate({ to: '/analysis', search: { machine } })
            }
          />
        </div>

        <Button onClick={run} disabled={loading}>
          <RefreshCw className={loading ? 'spin' : ''} />
          {loading ? 'Analyzing machine...' : 'Run machine analysis'}
        </Button>
      </div>

      <div className="demo-notice">
        <ScanLine size={18} />
        <div>
          <strong>
            {isMLResult
              ? 'TRAINED ML MODEL ANALYSIS'
              : isBackendResult
                ? 'BACKEND ANALYSIS'
                : 'DEMO DATA'}
          </strong>
          <p>
            {isMLResult
              ? 'The trained ML model returned a prediction for simulated machine readings. Other diagnostics may still contain demo data.'
              : isBackendResult
                ? 'A backend recommendation was received. Other diagnostics may still contain demo data.'
                : 'Sample diagnostics are shown until a backend analysis response is received.'}
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" className="error-notice">
          {error}
          <Button variant="outline" size="sm" onClick={run}>
            Retry
          </Button>
        </div>
      )}

      {notice && (
        <div role="status" className="success-notice">
          {notice}
        </div>
      )}

      <div className="analysis-readings">
        {[
          {
            label: 'Temperature',
            value: `${temp.convert(machine.temperature)} ${temp.unit}`,
          },
          {
            label: 'Rotational speed',
            value: `${machine.rpm.toLocaleString()} RPM`,
          },
          {
            label: 'Torque',
            value: `${machine.torque} N·m`,
          },
          {
            label: 'Tool wear',
            value: `${machine.wear} min`,
          },
        ].map((reading) => (
          <div key={reading.label}>
            <span>{reading.label}</span>
            <strong>{reading.value}</strong>
          </div>
        ))}
      </div>

      {analysis.recommendation && (
        <section className="diagnostic-panel">
          <div className="panel-heading">
            <h2>
              <TriangleAlert size={17} />
              Backend recommendation
            </h2>
            <Status status={analysis.severity} />
          </div>

          <div className="diagnostic-content">
            <p>{analysis.recommendation}</p>
          </div>
        </section>
      )}

      <div className="analysis-grid">
        <section className="diagnostic-panel">
          <div className="panel-heading">
            <h2>
              <TriangleAlert size={17} />
              {isBackendResult
                ? 'Sample anomaly history'
                : 'Detected sample anomalies'}
            </h2>
            <Status status={analysis.severity} />
          </div>

          <div className="diagnostic-content">
            {analysis.anomalies.map((anomaly, index) => (
              <div className="anomaly-item" key={anomaly}>
                <span className="number-marker">
                  0{index + 1}
                </span>
                <p>{anomaly}</p>
              </div>
            ))}

            <div className="confidence">
              <span>
                {isMLResult ? 'ML failure probability' : 'Sample confidence'}
                {!isMLResult && <> <DemoBadge /></>}
              </span>
              <strong>
                {isMLResult && typeof analysis.failureProbability === 'number'
                  ? `${(analysis.failureProbability * 100).toFixed(1)}%`
                  : `${analysis.confidence}%`}
              </strong>
            </div>

            <p className="muted-small">
              {isMLResult
                ? 'Probability returned by the trained model for these simulated readings; it is not a guarantee of failure.'
                : 'This confidence value is preconfigured demo data, not a model-generated score.'}
            </p>
          </div>
        </section>

        <section className="diagnostic-panel">
          <div className="panel-heading">
            <h2>
              <ScanLine size={17} />
              Possible failure causes
            </h2>
          </div>

          <div className="diagnostic-content">
            {analysis.causes.map((cause) => (
              <p className="cause-item" key={cause}>
                <ChevronRight size={16} />
                {cause}
              </p>
            ))}

            <p className="muted-small">
              Illustrative hypotheses only. Confirm against approved
              machine specifications.
            </p>
          </div>
        </section>
      </div>

      <section className="inspection-section">
        <div className="panel-heading">
          <h2>
            <ListChecks size={17} />
            Recommended inspection steps
          </h2>
          <span className="muted-small">Qualified personnel only</span>
        </div>

        <div className="inspection-list">
          {analysis.steps.map((step, index) => (
            <div key={step}>
              <span className="number-marker">
                {String(index + 1).padStart(2, '0')}
              </span>
              <p>{step}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="analysis-bottom">
        <span>
          {isBackendResult
            ? 'Backend response received · '
            : 'Sample analysis timestamp: '}
          {formatTimestamp(analysis.timestamp)}
        </span>

        <Button asChild variant="outline">
          <a
            href="/technician"
            onClick={(event) => {
              event.preventDefault();
              navigate({
                to: '/technician',
                search: { machine: machineId },
              });
            }}
          >
            <MessageSquare />
            Discuss with technician
          </a>
        </Button>
      </div>
    </>
  );
}