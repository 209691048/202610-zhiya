"""Rebuild diagrams 13 and 15, then apply stable, explicit edge ports.

The .puml files own nodes, labels and directed relations. PlantUML/Graphviz
owns the initial shapes. This file owns the two small routing corrections
that Graphviz did not satisfy: distinct APP output ports, and a planar DFD
placement with distinct P1 ports. It generates both final SVG and PNG.

Run with the bundled Python from the project root or any directory.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('ZHIYA_PROJECT_ROOT', HERE.parents[1]))
RUNTIME = Path(os.environ.get('LOCALAPPDATA', r'C:/Users/86134/AppData/Local')).parents[1] / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
JAVA = Path(os.environ.get('ZHIYA_JAVA', r'C:/Program Files/JetBrains/PyCharm 2026.1.2/jbr/bin/java.exe'))
NODE = Path(os.environ.get('ZHIYA_NODE', RUNTIME / 'node/bin/node.exe'))
SHARP = Path(os.environ.get('ZHIYA_SHARP', RUNTIME / 'node/node_modules/sharp'))
PLANTUML = Path(os.environ.get('PLANTUML_JAR', ROOT / 'work/plantuml.jar'))
DOT = Path(os.environ.get('GRAPHVIZ_DOT', ROOT / 'work/graphviz/Graphviz-16.1.0-win64/bin/dot.exe'))
NS = 'http://www.w3.org/2000/svg'
Q = '{' + NS + '}'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def groups(root, klass):
    return [g for g in root.iter(Q + 'g') if g.get('class') == klass]


def link(root, path_id):
    found = [g for g in groups(root, 'link') if g.find(Q + 'path').get('id') == path_id]
    assert len(found) == 1, path_id
    return found[0]


def entity(root, name):
    found = [g for g in root.iter(Q + 'g') if g.get('data-qualified-name') == name]
    assert len(found) == 1, name
    return found[0]


def fmt(n):
    return f'{n:.3f}'.rstrip('0').rstrip('.')


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    assert length > 0
    return dx / length, dy / length


def arrow(tip, previous):
    ux, uy = unit(previous, tip)
    nx, ny = -uy, ux
    tail = (tip[0] - 20.625 * ux, tip[1] - 20.625 * uy)
    neck = (tip[0] - 11.458 * ux, tip[1] - 11.458 * uy)
    points = [tip, (tail[0] + 9.167 * nx, tail[1] + 9.167 * ny), neck,
              (tail[0] - 9.167 * nx, tail[1] - 9.167 * ny), tip]
    return ' '.join(f'{fmt(x)},{fmt(y)}' for x, y in points)


def route(root, path_id, points, *, bidirectional=False, labels=None):
    g = link(root, path_id)
    p = g.find(Q + 'path')
    polygons = g.findall(Q + 'polygon')
    assert len(polygons) == (2 if bidirectional else 1), path_id
    body = list(points)
    if bidirectional:
        ux, uy = unit(points[0], points[1])
        body[0] = (points[0][0] + 11.458 * ux, points[0][1] + 11.458 * uy)
        polygons[0].set('points', arrow(points[0], points[1]))
    ux, uy = unit(points[-2], points[-1])
    body[-1] = (points[-1][0] - 11.458 * ux, points[-1][1] - 11.458 * uy)
    polygons[-1].set('points', arrow(points[-1], points[-2]))
    p.set('d', 'M' + ' L'.join(f'{fmt(x)},{fmt(y)}' for x, y in body))
    if labels is not None:
        texts = g.findall(Q + 'text')
        assert len(texts) == len(labels), path_id
        for text, (x, y) in zip(texts, labels):
            text.set('x', fmt(x))
            text.set('y', fmt(y))


def signature(root):
    """Geometry can change; model identity, relation direction and text cannot."""
    nodes = sorted((g.get('id'), g.get('data-qualified-name'))
                   for g in root.iter(Q + 'g') if g.get('class') in ('entity', 'cluster'))
    edges = sorted((g.get('data-entity-1'), g.get('data-entity-2'),
                    g.find(Q + 'path').get('id'), len(g.findall(Q + 'polygon')),
                    tuple(t.text for t in g.findall(Q + 'text')))
                   for g in groups(root, 'link'))
    texts = sorted(t.text or '' for t in root.iter(Q + 'text'))
    return nodes, edges, texts


def path_points(d):
    tokens = re.findall(r'[MLC]|-?\d+(?:\.\d+)?', d)
    out = []
    i = 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ('M', 'L'):
            out.append((float(tokens[i]), float(tokens[i + 1])))
            i += 2
        elif command == 'C':
            values = list(map(float, tokens[i:i + 6]))
            i += 6
            a, b, c, e = out[-1], values[:2], values[2:4], values[4:]
            for k in range(1, 13):
                t = k / 12
                u = 1 - t
                out.append((u*u*u*a[0] + 3*u*u*t*b[0] + 3*u*t*t*c[0] + t*t*t*e[0],
                            u*u*u*a[1] + 3*u*u*t*b[1] + 3*u*t*t*c[1] + t*t*t*e[1]))
        else:
            raise AssertionError(command)
    return out


def cross(a, b):
    return a[0]*b[1] - a[1]*b[0]


def segment_relation(a, b, c, d):
    r, s = (b[0]-a[0], b[1]-a[1]), (d[0]-c[0], d[1]-c[1])
    rr = r[0]*r[0] + r[1]*r[1]
    ss = s[0]*s[0] + s[1]*s[1]
    if rr < 0.001 or ss < 0.001:
        return None
    q = (c[0]-a[0], c[1]-a[1])
    det = cross(r, s)
    if abs(det) < 1e-5 * math.sqrt(rr*ss):
        if abs(cross(q, r)) / math.sqrt(rr) > 0.1:
            return None
        t0 = (q[0]*r[0]+q[1]*r[1])/rr
        t1 = t0 + (s[0]*r[0]+s[1]*r[1])/rr
        shared = (min(1, max(t0, t1)) - max(0, min(t0, t1))) * math.sqrt(rr)
        return 'shared' if shared > 0.5 else None
    t, u = cross(q, s)/det, cross(q, r)/det
    return 'crossing' if 1e-6 < t < 1-1e-6 and 1e-6 < u < 1-1e-6 else None


def route_diagnostics(root):
    paths = [(g.find(Q+'path').get('id'), path_points(g.find(Q+'path').get('d')))
             for g in groups(root, 'link')]
    result = {'shared_segments': [], 'crossing_pairs': []}
    for n, (name1, pts1) in enumerate(paths):
        for name2, pts2 in paths[n + 1:]:
            relations = {segment_relation(a, b, c, d)
                         for a, b in zip(pts1, pts1[1:])
                         for c, d in zip(pts2, pts2[1:])}
            if 'shared' in relations:
                result['shared_segments'].append([name1, name2])
            if 'crossing' in relations:
                result['crossing_pairs'].append([name1, name2])
    return result


def hits_box(a, b, box):
    """Test open segment against a slightly inset rectangular obstacle."""
    x0, y0, x1, y1 = box
    dx, dy = b[0]-a[0], b[1]-a[1]
    lo, hi = 0.0, 1.0
    for p, q in [(-dx, a[0]-x0), (dx, x1-a[0]), (-dy, a[1]-y0), (dy, y1-a[1])]:
        if abs(p) < 1e-9:
            if q < 0:
                return False
        elif p < 0:
            lo = max(lo, q/p)
        else:
            hi = min(hi, q/p)
    return lo < hi and hi > 0 and lo < 1


def obstacle_diagnostics(root):
    node_boxes, text_boxes = [], []
    for g in root.iter(Q+'g'):
        shift = list(map(float, re.findall(r'-?\d+(?:\.\d+)?', g.get('transform', ''))))
        tx, ty = shift if len(shift) == 2 else (0.0, 0.0)
        if g.get('class') == 'entity':
            xy = []
            outline = None
            for c in g:
                kind = c.tag.split('}')[-1]
                if kind == 'rect':
                    x, y, w, h = [float(c.get(k)) for k in ('x','y','width','height')]
                    xy += [(x,y), (x+w,y+h)]
                elif kind in ('polygon','path'):
                    values = list(map(float,re.findall(r'-?\d+(?:\.\d+)?',c.get('points',c.get('d','')))))
                    xy += list(zip(values[0::2], values[1::2]))
                    if kind == 'polygon' and outline is None:
                        outline = [(x+tx,y+ty) for x,y in zip(values[0::2],values[1::2])]
            if xy:
                node_boxes.append((g.get('data-qualified-name'),
                                   (min(x for x,y in xy)+tx+1, min(y for x,y in xy)+ty+1,
                                    max(x for x,y in xy)+tx-1, max(y for x,y in xy)+ty-1), outline))
        for t in g.findall(Q+'text'):
            x, y, fs, width = [float(t.get(k)) for k in ('x','y','font-size','textLength')]
            text_boxes.append((t.text, (x+tx, y+ty-fs*.90, x+tx+width, y+ty+fs*.18)))
    result = {'node_body_hits': [], 'label_box_hits': []}
    for g in groups(root,'link'):
        p = g.find(Q+'path')
        points = path_points(p.get('d'))
        for name, box, outline in node_boxes:
            # Folder tabs are non-rectangular: their empty upper-right area
            # is a valid approach channel, not a node-body collision.
            hit = any(hits_polygon(a,b,outline) if outline else hits_box(a,b,box)
                      for a,b in zip(points,points[1:]))
            if hit:
                result['node_body_hits'].append([p.get('id'),name])
        for name, box in text_boxes:
            if any(hits_box(a,b,box) for a,b in zip(points,points[1:])):
                result['label_box_hits'].append([p.get('id'),name])
    return result


def hits_polygon(a, b, polygon):
    def inside(point):
        x, y = point
        result = False
        for c, d in zip(polygon,polygon[1:]+polygon[:1]):
            dx,dy=d[0]-c[0],d[1]-c[1]
            length=math.hypot(dx,dy)
            if length and abs(cross((x-c[0],y-c[1]),(dx,dy)))/length < 0.1:
                if min(c[0],d[0])-0.1 <= x <= max(c[0],d[0])+0.1 and min(c[1],d[1])-0.1 <= y <= max(c[1],d[1])+0.1:
                    return False
            if (c[1]>y)!=(d[1]>y) and x < (d[0]-c[0])*(y-c[1])/(d[1]-c[1])+c[0]:
                result=not result
        return result
    return inside(a) or inside(b) or any(segment_relation(a,b,c,d)=='crossing'
        for c,d in zip(polygon,polygon[1:]+polygon[:1]))


def fix13(root):
    assert root.get('viewBox') == '0 0 1782 2073', 'Reroute coordinates need review after model/layout change.'
    # Previously APP->DB and APP->TMP shared 37px from the same APP port.
    # TMP now uses x=300 on APP's bottom edge, far left of the DB port x=878.
    route(root, 'APP-to-TMP', [(300, 1352.817), (300, 1605.542)], labels=[(110, 1460)])


def fix15(root):
    assert root.get('viewBox') == '0 0 1849 2032', 'Reroute coordinates need review after model/layout change.'
    # Keep all shapes, IDs and text. Put D3 beside P2 and P4 on the next rank.
    # The P2-D3-P4-D2 cycle is now planar instead of a bow-tie crossing.
    entity(root, 'D3').set('transform', 'translate(150 -400)')
    entity(root, 'P4').set('transform', 'translate(0 400)')
    # P1->P2 leaves a dedicated right-side port, not beside the D1 arrowhead.
    route(root, 'P1-to-P2', [(397.995, 490), (500, 490), (500, 700), (546.035, 802.885)])
    route(root, 'P2-D3', [(794.453, 845), (1010.521, 845)], bidirectional=True,
          labels=[(815, 760), (815, 811.418)])
    route(root, 'P2-D2', [(794.453, 900), (935, 1000), (1197.327, 1000), (1286.015, 1569.448)],
          bidirectional=True, labels=[(970, 1242.330), (970, 1293.749)])
    route(root, 'ADMIN-to-P4', [(1570.869, 511.241), (1570.869, 1156.960)],
          labels=[(1586.910, 840), (1606.390, 891.418)])
    route(root, 'P4-to-D3', [(1530, 1156.960), (1530, 1000), (1303.737, 860)],
          labels=[(1320, 1033.926), (1320, 1085.344)])
    route(root, 'P4-to-D2', [(1586.154, 1333.130), (1573.160, 1390), (1383.754, 1569.471)],
          labels=[(1550, 1450), (1530, 1501.418)])


def rasterize(svg, png, width, height, font_env):
    js = "const sharp=require(process.argv[1]);sharp(process.argv[2]).resize(+process.argv[4],+process.argv[5],{fit:'fill'}).flatten({background:'#fff'}).png().toFile(process.argv[3]).catch(e=>{console.error(e);process.exit(1)});"
    subprocess.run([str(NODE), '-e', js, str(SHARP), str(svg), str(png), str(width), str(height)],
                   env=font_env, check=True)


def main():
    env = os.environ.copy()
    env['GRAPHVIZ_DOT'] = str(DOT)
    with tempfile.TemporaryDirectory(prefix='zhiya-13-15-font-') as cache:
        config = Path(cache) / 'fonts.conf'
        config.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
                          '<fontconfig><dir>C:/Windows/Fonts</dir><cachedir>'+Path(cache).as_posix()+
                          '/cache</cachedir></fontconfig>',encoding='utf-8')
        font_env = env.copy()
        font_env['FONTCONFIG_FILE'] = str(config)
        for name, fix, max_height in [('fig-8-01-deployment', fix13, 15.5), ('fig-4-02-data-flow', fix15, 15)]:
            rebuild(name, fix, max_height, env, font_env)


def rebuild(name, fix, max_height, env, font_env):
        source, svg = HERE / (name + '.puml'), HERE / (name + '.svg')
        subprocess.run([str(JAVA), '-Djava.awt.headless=true', '-jar', str(PLANTUML),
                        '-charset', 'UTF-8', '-tsvg', str(source)], env=env, check=True)
        tree = ET.parse(svg)
        root = tree.getroot()
        before_signature = signature(root)
        before_routes = route_diagnostics(root)
        fix(root)
        assert signature(root) == before_signature, 'Model content must not change.'
        after_routes = route_diagnostics(root)
        assert not after_routes['shared_segments'], after_routes
        assert not after_routes['crossing_pairs'], after_routes
        obstacles = obstacle_diagnostics(root)
        assert not obstacles['node_body_hits'], obstacles
        assert not obstacles['label_box_hits'], obstacles
        meta = ET.SubElement(root, Q + 'metadata')
        meta.text = 'Deterministic post-layout routing: 13-15-route.py. Nodes, text and relation identities are checked against PlantUML output.'
        tree.write(svg, encoding='utf-8', xml_declaration=True)
        _, _, w, h = map(float, root.get('viewBox').split())
        rasterize(svg, HERE / (name + '.png'), int(w), int(h), font_env)
        min_font = min(float(t.get('font-size')) for t in root.iter(Q + 'text'))
        scale = min(17 / w, max_height / h)
        print(json.dumps({'diagram': name, 'before': before_routes, 'after': after_routes,
                          'obstacles': obstacles,
                          'cm': [round(w*scale, 3), round(h*scale, 3)],
                          'minimum_font_pt': round(min_font*scale*72/2.54, 3)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
