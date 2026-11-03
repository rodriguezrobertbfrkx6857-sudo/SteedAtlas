export function toRows(project) {
 let tick=0;
 const visual=[],subtitles=[];
 for(const s of project.scenes){
  const start=tick/project.fps_num;tick+=s.duration_ticks;const end=tick/project.fps_num;
  visual.push({id:s.id,start,end,effectId:'visual',movable:false});
  subtitles.push({id:'sub-'+s.id,start,end,effectId:'subtitle',movable:false,flexible:false});
 }
 return [{id:'visual',actions:visual},{id:'audio',actions:project.audio_asset_ids.length?[{id:'audio',start:0,end:tick/project.fps_num,effectId:'audio',movable:false,flexible:false}]:[]},{id:'subtitle',actions:subtitles}];
}
export function applyRows(project,rows) {
 const row=rows.find(x=>x.id==='visual');
 if(!row||row.actions.length!==project.scenes.length)throw new Error('INVALID_TIMELINE_ROW');
 const scenes=row.actions.map(a=>{
  const s=project.scenes.find(x=>x.id===a.id);
  if(!s||!Number.isFinite(a.start)||!Number.isFinite(a.end)||a.end<=a.start)throw new Error('INVALID_CLIP_RANGE');
  const duration_ticks=Math.round((a.end-a.start)*project.fps_num);
  if(duration_ticks<24||duration_ticks>1440)throw new Error('CLIP_DURATION_LIMIT');
  return {...s,duration_ticks};
 });
 if(new Set(scenes.map(s=>s.id)).size!==scenes.length)throw new Error('DUPLICATE_CLIP');
 return {...project,scenes};
}
