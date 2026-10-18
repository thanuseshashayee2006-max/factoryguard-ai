import type { Health } from './machines';
export interface MachineAlert {id:string; machineId:string; severity:Health; description:string; timestamp:string; status:'Open'|'Acknowledged'|'Resolved'; source?:'demo'|'trained-ml'; machineName?:string; failureProbability?:number}
export const mockAlerts: MachineAlert[] = [
{id:'ALT-1042',machineId:'MCH-003',severity:'Critical',description:'Spindle temperature deviation',timestamp:'2026-10-12T08:42:00Z',status:'Open'},
{id:'ALT-1041',machineId:'MCH-002',severity:'Warning',description:'Torque variation detected',timestamp:'2026-10-12T08:36:00Z',status:'Open'},
{id:'ALT-1040',machineId:'MCH-006',severity:'Warning',description:'Temperature trend flagged for review',timestamp:'2026-10-12T08:28:00Z',status:'Open'},
{id:'ALT-1039',machineId:'MCH-003',severity:'Critical',description:'Irregular spindle speed pattern',timestamp:'2026-10-12T07:55:00Z',status:'Acknowledged'},
{id:'ALT-1038',machineId:'MCH-005',severity:'Warning',description:'Tool inspection scheduled',timestamp:'2026-10-11T15:20:00Z',status:'Resolved'},
{id:'ALT-1037',machineId:'MCH-001',severity:'Healthy',description:'Preventive maintenance completed',timestamp:'2026-10-11T11:15:00Z',status:'Resolved'},
{id:'ALT-1036',machineId:'MCH-006',severity:'Warning',description:'Cooling circuit inspection required',timestamp:'2026-10-10T14:30:00Z',status:'Acknowledged'},
];
