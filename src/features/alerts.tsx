import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Search, ArrowUpRight, Check, CheckCheck, History } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/services/api';
import {
  PageHeading,
  DemoBadge,
  FilterSelect,
  healthOptions,
  Status,
  EmptyState,
} from '@/components/factoryguard/shared';
import { useFactory, formatTimestamp } from '@/components/factoryguard/state';

export function AlertsPage() {
  const { alerts, updateAlert } = useFactory();
  const [search, setSearch] = useState('');
  const [severity, setSeverity] = useState('all');
  const [machine, setMachine] = useState('all');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  const filtered = alerts.filter(
    (a) =>
      (severity === 'all' || severity === a.severity) &&
      (machine === 'all' || machine === a.machineId) &&
      `${a.id} ${a.machineId} ${a.description} ${a.status} ${a.source ?? 'demo'}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  async function changeStatus(id: string, status: 'Acknowledged' | 'Resolved') {
    setBusyId(id);
    setNotice('');

    try {
      await updateAlert(id, status);
      const alert = alerts.find((a) => a.id === id);
      const isML = alert?.source === 'trained-ml';

      setNotice(
        `${id} ${status.toLowerCase()}${isML ? ' and saved to the backend.' : ' in this demo session.'}`,
      );
    } catch (error) {
      setNotice(
        error instanceof Error
          ? `Could not update ${id}: ${error.message}`
          : `Could not update ${id}. Please try again.`,
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeading
        title="Alerts & History"
        description="Review machine events and track maintenance actions."
      >
        <DemoBadge />
      </PageHeading>

      <div className="alert-summary">
        {['Open', 'Acknowledged', 'Resolved'].map((s) => (
          <div key={s}>
            <span>{s} alerts</span>
            <strong>
              {String(alerts.filter((a) => a.status === s).length).padStart(2, '0')}
            </strong>
          </div>
        ))}
      </div>

      {notice && (
        <div role="status" className="success-notice">
          {notice}
        </div>
      )}

      <div className="table-panel">
        <div className="panel-heading">
          <h2>
            <History size={16} />
            Event history
          </h2>
          <span className="muted-small">All timestamps in UTC</span>
        </div>

        <div className="table-toolbar">
          <div className="search-input">
            <Search size={15} />
            <Input
              aria-label="Search alerts"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search alerts, machines or descriptions..."
            />
          </div>

          <div className="filter-group">
            <FilterSelect
              value={severity}
              onChange={setSeverity}
              label="Filter alert severity"
              options={healthOptions.map((o) =>
                o.value === 'all' ? { ...o, label: 'All severities' } : o,
              )}
            />
            <FilterSelect
              value={machine}
              onChange={setMachine}
              label="Filter alert machine"
              options={[
                { value: 'all', label: 'All machines' },
                ...api.listMachines().map((m) => ({ value: m.id, label: m.id })),
              ]}
            />
          </div>
        </div>

        <div className="table-scroll">
          <table className="data-table alerts-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Machine</th>
                <th>Severity</th>
                <th>Description</th>
                <th>Source</th>
                <th>Timestamp</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => {
                const isML = a.source === 'trained-ml';

                return (
                  <tr key={a.id}>
                    <td className="machine-id">{a.id}</td>
                    <td>
                      <Link
                        to="/machines/$machineId"
                        params={{ machineId: a.machineId }}
                        className="text-link"
                      >
                        {a.machineId}
                        <ArrowUpRight size={12} />
                      </Link>
                    </td>
                    <td>
                      <Status status={a.severity} />
                    </td>
                    <td>{a.description}</td>
                    <td>{isML ? 'Trained ML' : 'Demo'}</td>
                    <td className="time-cell">{formatTimestamp(a.timestamp)}</td>
                    <td>
                      <span className={`event-status event-${a.status.toLowerCase()}`}>
                        {a.status}
                      </span>
                    </td>
                    <td>
                      <div className="alert-actions">
                        {a.status === 'Open' && (
                          <Button
                            size="icon"
                            variant="ghost"
                            title={isML ? 'Acknowledge ML alert' : 'Acknowledge demo alert'}
                            aria-label={`Acknowledge ${a.id}`}
                            disabled={busyId === a.id}
                            onClick={() => void changeStatus(a.id, 'Acknowledged')}
                          >
                            <Check size={16} />
                          </Button>
                        )}
                        {a.status !== 'Resolved' && (
                          <Button
                            size="icon"
                            variant="ghost"
                            title={isML ? 'Resolve ML alert' : 'Resolve demo alert'}
                            aria-label={`Resolve ${a.id}`}
                            disabled={busyId === a.id}
                            onClick={() => void changeStatus(a.id, 'Resolved')}
                          >
                            <CheckCheck size={16} />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!filtered.length && (
          <EmptyState
            title="No matching alerts"
            detail="Try another search, severity or machine filter."
          />
        )}

        <div className="table-footer">
          <span>{filtered.length} events</span>
          <span>ML alert status changes are saved to the backend.</span>
        </div>
      </div>
    </>
  );
}
