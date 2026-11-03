import type { TimelineRow } from '@xzdarcy/react-timeline-editor';
export function toRows(project:any):TimelineRow[];
export function applyRows<T>(project:T,rows:TimelineRow[]):T;
