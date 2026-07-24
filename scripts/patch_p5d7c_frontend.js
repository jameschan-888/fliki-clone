const fs = require('fs');
const EOL = (b) => b.includes(Buffer.from([13, 10])) ? '\r\n' : '\n';

function patch(p, edits) {
  const raw = fs.readFileSync(p);
  const eol = EOL(raw);
  let src = raw.toString('utf8');
  for (const [find, repl] of edits) {
    if (!src.includes(find)) { console.error('miss in ' + p + ' :: ' + find.slice(0, 60)); process.exit(1); }
    src = src.replace(find, repl);
  }
  fs.writeFileSync(p, src);
  console.log('OK ' + p);
}

patch('D:/workspace/Fliki视频制作还原/app/src/types/draft.ts', [
  ['  avatar?: string | null;\n};', '  avatar?: string | null;\n  avatar_layout?: Record<string, unknown> | null;\n};'],
]);

patch('D:/workspace/Fliki视频制作还原/app/src/api/drafts.ts', [
  ['      avatar: scene.avatar ?? null,\n    }),\n  );', '      avatar: scene.avatar ?? null,\n      avatar_layout: scene.avatar_layout ?? undefined,\n    }),\n  );'],
]);