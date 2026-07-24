const fs = require('fs');
function patch(p, edits) {
  let src = fs.readFileSync(p, 'utf8');
  for (const [find, repl] of edits) {
    if (!src.includes(find)) { console.error('miss ' + p + ' :: ' + find.slice(0, 60)); process.exit(1); }
    src = src.replace(find, repl);
  }
  fs.writeFileSync(p, src);
  console.log('OK ' + p);
}
patch('D:/workspace/Fliki视频制作还原/backend/tests/test_p5d7_avatar_layout.py', [
  ['class _RenderBody:\n    def __init__(self, playback_id, props_path):\n        self.playback_id = playback_id\n        self.props_path = props_path', 'class _RenderBody:\n    def __init__(self, playback_id, props_path, **kwargs):\n        self.playback_id = playback_id\n        self.props_path = props_path\n        self.kwargs = kwargs'],
]);
patch('D:/workspace/Fliki视频制作还原/backend/tests/test_p5d7b_avatar_layout_extra.py', [
  ['class _RenderBody:\n    def __init__(self, playback_id, props_path):\n        self.playback_id = playback_id\n        self.props_path = props_path', 'class _RenderBody:\n    def __init__(self, playback_id, props_path, **kwargs):\n        self.playback_id = playback_id\n        self.props_path = props_path\n        self.kwargs = kwargs'],
]);
patch('D:/workspace/Fliki视频制作还原/backend/tests/test_p5d6_avatar_render.py', [
  ['class _RenderBody:\n    def __init__(self, playback_id, props_path):\n        self.playback_id = playback_id\n        self.props_path = props_path', 'class _RenderBody:\n    def __init__(self, playback_id, props_path, **kwargs):\n        self.playback_id = playback_id\n        self.props_path = props_path\n        self.kwargs = kwargs'],
]);