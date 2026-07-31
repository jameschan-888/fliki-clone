#!/usr/bin/env python
# P7C-B: 本地视频模板渲染器 (Remotion 模板的本地轻量替代).
# 解析 template + fields -> RenderPlan. 不真跑渲染, 留给下游 ffmpeg / Remotion.
# 视频额度测试期间 mode 默认 mock, 不下发任何 ffmpeg / Remotion 任务.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LayerPlan:
    type: str
    text: str | None = None
    position: str | None = None
    x: int | None = None
    y: int | None = None
    font_size: int | None = None
    color: str | None = None
    bg_color: str | None = None
    animation: str | None = None
    delay: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {'type': self.type}
        if self.text is not None: out['text'] = self.text
        if self.position is not None: out['position'] = self.position
        if self.x is not None: out['x'] = self.x
        if self.y is not None: out['y'] = self.y
        if self.font_size is not None: out['font_size'] = self.font_size
        if self.color is not None: out['color'] = self.color
        if self.bg_color is not None: out['bg_color'] = self.bg_color
        if self.animation is not None: out['animation'] = self.animation
        if self.delay is not None: out['delay'] = self.delay
        if self.extras: out.update(self.extras)
        return out


@dataclass
class RenderPlan:
    template_id: str
    background: dict[str, Any]
    layers: list[LayerPlan]
    duration_seconds: float
    aspect_ratio: str
    provider: str  # 'mock' | 'ffmpeg' | 'remotion'
    placeholder_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'template_id': self.template_id,
            'background': self.background,
            'layers': [layer.to_dict() for layer in self.layers],
            'duration_seconds': self.duration_seconds,
            'aspect_ratio': self.aspect_ratio,
            'provider': self.provider,
            'placeholder_path': self.placeholder_path,
            'layer_count': len(self.layers),
        }


class TemplateRenderError(RuntimeError):
    pass


def _resolve_text(layer_def, user_fields):
    text_field = layer_def.get('text_field')
    if text_field and text_field in user_fields and user_fields[text_field]:
        return str(user_fields[text_field])
    if 'text' in layer_def:
        return str(layer_def['text'])
    if text_field:
        return '{' + text_field + '}'
    return None


class TemplateRenderer:
    def __init__(self, template, user_fields, *, mode='mock', scene_id=None, duration_override=None):
        self.template = template
        self.user_fields = user_fields or {}
        self.mode = mode
        self.scene_id = scene_id
        self.duration_override = duration_override

    @property
    def template_id(self):
        return self.template['id']

    def resolve_layer(self, layer_def):
        extras = {}
        for key in ('index', 'size', 'max_width', 'line_height', 'font_weight',
                    'padding', 'prefix', 'width', 'height', 'title_field', 'desc_field'):
            if key in layer_def:
                extras[key] = layer_def[key]
        if layer_def.get('type') == 'step_card' and 'index' in layer_def:
            idx = layer_def['index']
            title_field = layer_def.get('title_field') or ('step' + str(idx) + '_title')
            desc_field = layer_def.get('desc_field') or ('step' + str(idx) + '_desc')
            title = self.user_fields.get(title_field, '{missing}')
            desc = self.user_fields.get(desc_field, '')
            text = ('Step ' + str(idx) + ': ' + str(title)) + (' - ' + str(desc) if desc else '')
        else:
            text = _resolve_text(layer_def, self.user_fields)

        return LayerPlan(
            type=layer_def.get('type', 'text'),
            text=text,
            position=layer_def.get('position'),
            x=layer_def.get('x'),
            y=layer_def.get('y'),
            font_size=layer_def.get('font_size'),
            color=layer_def.get('color'),
            bg_color=layer_def.get('bg_color'),
            animation=layer_def.get('animation'),
            delay=layer_def.get('delay'),
            extras=extras,
        )

    def build_plan(self):
        structure = self.template.get('structure') or {}
        bg = structure.get('background') or {'type': 'solid', 'color': '#000000'}
        layers = [self.resolve_layer(layer) for layer in structure.get('layers', [])]
        duration = float(self.duration_override or structure.get('duration_seconds') or 5.0)
        aspect = structure.get('aspect_ratio') or '16:9'
        placeholder = None
        if self.mode == 'mock' and self.scene_id:
            placeholder = 'templates/' + self.template_id + '/mock-' + self.scene_id + '.mp4'
        return RenderPlan(
            template_id=self.template_id,
            background=bg,
            layers=layers,
            duration_seconds=duration,
            aspect_ratio=aspect,
            provider=self.mode,
            placeholder_path=placeholder,
        )

    def render(self, destination=None):
        plan = self.build_plan()
        payload = {'ok': True, 'mock': self.mode == 'mock', 'plan': plan.to_dict()}
        if self.mode == 'ffmpeg':
            payload['ffmpeg_commands'] = self._build_ffmpeg_commands(plan)
        elif self.mode == 'remotion':
            payload['react_source'] = self._build_remotion_source(plan)
        if destination is not None:
            payload['destination'] = str(destination)
        return payload

    def _build_ffmpeg_commands(self, plan):
        cmds = []
        bg = plan.background
        if bg.get('type') == 'gradient':
            colors = bg.get('colors', ['#000', '#111'])
            cmds.append('gradbg=colors=' + ':'.join(colors))
        elif bg.get('type') == 'solid':
            color_val = bg.get('color', '#000000')
            cmds.append('color=c=' + color_val + ':s=1280x720:d=' + str(plan.duration_seconds))
        for layer in plan.layers:
            if layer.type in ('text', 'title', 'subtitle', 'logo_text', 'cta_button', 'step_card',
                              'big_number', 'unit', 'author', 'big_quote'):
                color_val = layer.color or '#ffffff'
                cmds.append('drawtext=text=' + chr(39) + str(layer.text) + chr(39) +
                            ':fontsize=' + str(layer.font_size or 32) +
                            ':fontcolor=' + color_val +
                            ':x=(w-text_w)/2:y=' + str(layer.y or 0))
        return cmds

    def _build_remotion_source(self, plan):
        lines = []
        for layer in plan.layers:
            txt = json.dumps(layer.text, ensure_ascii=False) if layer.text is not None else 'null'
            lines.append('      {/* ' + layer.type + ' y=' + str(layer.y) + ' text=' + txt + ' */}')
        layers_jsx = chr(92) + 'n'.join(lines)
        bg_color = plan.background.get('color', '#000')
        return ('import {AbsoluteFill, useCurrentFrame} from ' + chr(34) + 'remotion' + chr(34) + ';' + chr(92) + 'n' +
                chr(92) + 'n' +
                'export default function Template_' + plan.template_id + '() {' + chr(92) + 'n' +
                '  const frame = useCurrentFrame();' + chr(92) + 'n' +
                '  return (' + chr(92) + 'n' +
                '    <AbsoluteFill style={{background: ' + chr(34) + bg_color + chr(34) + '}}>' + chr(92) + 'n' +
                layers_jsx + chr(92) + 'n' +
                '    </AbsoluteFill>' + chr(92) + 'n' +
                '  );' + chr(92) + 'n' +
                '}' + chr(92) + 'n')


def render_template(template, user_fields, *, mode='mock', scene_id=None, duration_override=None, destination=None):
    return TemplateRenderer(
        template, user_fields,
        mode=mode, scene_id=scene_id, duration_override=duration_override,
    ).render(destination)
