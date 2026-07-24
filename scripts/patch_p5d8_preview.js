const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/workflow_pipeline.py';
let src = fs.readFileSync(P, 'utf8');
const CRLF = '\r\n';

const oldEp = 'def execute_pipeline(run_id,get_db,render_create,render_body_class,background_tasks):';
const newEp = 'def execute_pipeline(run_id,get_db,render_create,render_body_class,background_tasks,preview=False):';
if (!src.includes(oldEp)) { console.error('execute_pipeline anchor miss'); process.exit(1); }
src = src.replace(oldEp, newEp);

const oldAv = '            if scene["avatar"]:' + CRLF + '                avatar_node=ensure_node';
const newAv = '            if scene["avatar"] and not preview:' + CRLF + '                avatar_node=ensure_node';
if (!src.includes(oldAv)) { console.error('avatar anchor miss'); process.exit(1); }
src = src.replace(oldAv, newAv);

const oldRd = '        response=render_create(render_body_class(playback_id=f"workflow-{run_id}",props_path=str(props_path)),background_tasks)';
const newRd = '        resolution="480p" if preview else "720p"' + CRLF + '        response=render_create(render_body_class(playback_id=f"workflow-{run_id}",props_path=str(props_path),resolution=resolution),background_tasks)';
if (!src.includes(oldRd)) { console.error('render_create anchor miss'); process.exit(1); }
src = src.replace(oldRd, newRd);

const oldCr = '    @router.post("/from-draft/{draft_id}")' + CRLF + '    def create_run(draft_id:str,background_tasks:BackgroundTasks):';
const newCr = '    @router.post("/from-draft/{draft_id}")' + CRLF + '    def create_run(draft_id:str,background_tasks:BackgroundTasks,preview:bool=False):';
if (!src.includes(oldCr)) { console.error('create_run anchor miss'); process.exit(1); }
src = src.replace(oldCr, newCr);

const oldBt = 'background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks)';
const newBt = 'background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks,preview)';
if (!src.includes(oldBt)) { console.error('add_task anchor miss'); process.exit(1); }
src = src.replace(oldBt, newBt);

const oldRt = '    @router.post("/{run_id}/retry")' + CRLF + '    def retry_run(run_id:str,background_tasks:BackgroundTasks):';
const newRt = '    @router.post("/{run_id}/retry")' + CRLF + '    def retry_run(run_id:str,background_tasks:BackgroundTasks,preview:bool=False):';
if (!src.includes(oldRt)) { console.error('retry_run anchor miss'); process.exit(1); }
src = src.replace(oldRt, newRt);

fs.writeFileSync(P, src);
console.log('OK');