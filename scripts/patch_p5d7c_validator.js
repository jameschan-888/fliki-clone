const fs = require('fs');
const P = 'D:/workspace/Fliki视频制作还原/backend/workflow_drafts.py';
let src = fs.readFileSync(P, 'utf8');
const old = `    def require_change(self):\r\n        if not self.model_fields_set:\r\n            raise ValueError("At least one scene field is required")\r\n        return self`;
const nw = `    def require_change(self):\r\n        # avatar_layout: dict | None = None 默认 None 不进 model_fields_set；用 model_dump(exclude_unset=True) 更稳\r\n        if not self.model_dump(exclude_unset=True):\r\n            raise ValueError("At least one scene field is required")\r\n        return self`;
if (!src.includes(old)) { console.error('validator miss'); process.exit(1); }
src = src.replace(old, nw);
fs.writeFileSync(P, src);
console.log('OK');