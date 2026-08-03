import { useEffect, useRef, useState } from "react";

const KEYWORDS = ["AI", "视频", "图片", "生成", "渲染", "脚本", "声音", "字幕", "字幕", "配乐", "场景", "对话", "特效", "转场"];

function highlight(text: string): string {
  var escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  KEYWORDS.forEach(function (kw) {
    var re = new RegExp("(" + kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "g");
    escaped = escaped.replace(re, "<mark>$1</mark>");
  });
  return escaped;
}

export type RichScriptEditorProps = {
  initial?: string;
  onChange?: (text: string) => void;
  rows?: number;
  readOnly?: boolean;
};

export function RichScriptEditor(props: RichScriptEditorProps) {
  var _t = useState(props.initial || ""), text = _t[0], setText = _t[1];
  var ref = useRef<HTMLTextAreaElement | null>(null);
  var prev = useRef<HTMLDivElement | null>(null);

  useEffect(function () {
    if (props.onChange) props.onChange(text);
  }, [text]);

  function sync() {
    if (prev.current && ref.current) {
      prev.current.scrollTop = ref.current.scrollTop;
      prev.current.scrollLeft = ref.current.scrollLeft;
    }
  }

  var wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  var charCount = text.length;
  var lineCount = text.split("\n").length;
  var estSeconds = Math.max(3, Math.round(wordCount / 2.5));

  return (
    <div className="richEditor">
      <div className="richEditorToolbar">
        <span className="eyebrow">SCRIPT</span>
        <div className="richActions">
          <span className="richMeta">📝 {charCount} 字 · {wordCount} 词 · {lineCount} 行</span>
          <span className="richMeta">⏱ 约 {estSeconds}s 配音</span>
          {text.length > 0 && (
            <button className="richBtn" onClick={function () { setText(""); }}>清空</button>
          )}
        </div>
      </div>
      <div className="richEditorWrap">
        <div ref={prev} className="richPreview" aria-hidden="true" dangerouslySetInnerHTML={{ __html: highlight(text) + String.fromCharCode(0x00a0) }} />
        <textarea
          ref={ref}
          className="richTextarea"
          value={text}
          rows={props.rows || 8}
          readOnly={props.readOnly}
          onScroll={sync}
          onChange={function (e) { setText(e.target.value); }}
          placeholder="在此撰写或粘贴脚本. 关键词会自动高亮."
          spellCheck={false}
        />
      </div>
      <div className="richFooter">
        <small>支持中英文 · 关键词高亮 · 实时统计字数和配音时长</small>
      </div>
    </div>
  );
}

export default RichScriptEditor;
