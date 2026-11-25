"""Pillow renderer for generated SDK TUI pages; uses source PNGs and logical coordinates."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = Path(__file__).resolve().parent / "fonts"

def font(path: Path, size: float):
    size = max(8, round(size))
    if "Roboto" in str(path):
        f = FONT_DIR / "Roboto-Bold.ttf"
    elif "Semi" in str(path):
        f = FONT_DIR / "TitilliumWeb-SemiBold.ttf"
    else:
        f = FONT_DIR / "TitilliumWeb-Regular.ttf"
    if not f.is_file(): return ImageFont.load_default()
    return ImageFont.truetype(str(f), size)

def rgba(hex_color: str):
    value = str(hex_color).removeprefix("#")
    if len(value) == 8: return tuple(bytes.fromhex(value))
    if len(value) == 6: return (*bytes.fromhex(value), 255)
    return (240,245,248,255)

def shown(item, values):
    for cond in item.get("conditions", []):
        v = values.get(cond["parameter"], 0.0)
        selected = round(max(0.0,min(1.0,v))*(cond["count"]-1))
        if selected != cond["index"]: return False
    return True

def render_page(model, page_index, values, display, name, out_path: Path):
    page = model["pages"][page_index]
    skin_dir = Path(model["skin_dir"])
    canvas = Image.new("RGBA", (page["width"],page["height"]), (18,23,26,255))
    if page.get("background") and (skin_dir/page["background"]).is_file():
        bg = Image.open(skin_dir/page["background"]).convert("RGBA").resize(canvas.size)
        canvas.alpha_composite(bg)
    d = ImageDraw.Draw(canvas)
    overflow = []
    for item in page["items"]:
        if not shown(item, values): continue
        x,y,w,h = [round(item[k]) for k in ("x","y","w","h")]
        typ=item["type"]
        if typ == "image":
            p=skin_dir/item["src"]
            if p.is_file(): canvas.alpha_composite(Image.open(p).convert("RGBA").resize((w,h)),(x,y))
        elif typ == "film":
            p=skin_dir/item["src"]
            if p.is_file():
                sheet=Image.open(p).convert("RGBA"); frames=max(1,item.get("frames",127)); fh=sheet.height//frames
                v=max(0.0,min(1.0,values.get(item.get("param"),0.0)))
                frame=round(v*(frames-1)); frame=(frames-1-frame) if item.get("invert") else frame
                crop=sheet.crop((0,frame*fh,sheet.width,(frame+1)*fh)).resize((w,h))
                canvas.alpha_composite(crop,(x,y))
        elif typ == "button":
            active=values.get(item.get("param"),0.0)>=0.5
            p=skin_dir/(item.get("on") if active else item.get("off"))
            if p.is_file(): canvas.alpha_composite(Image.open(p).convert("RGBA").resize((w,h)),(x,y))
        elif typ == "slider":
            # Slider lacks track/thumb art in V4.1 TUI. The frame and parameter are exact;
            # this stock-widget approximation is visibly outlined as such in browser mode.
            d.rounded_rectangle((x+8,y+h*0.44,x+w-8,y+h*0.56),radius=5,fill=(42,58,63,255))
            v=max(0.0,min(1.0,values.get(item.get("param"),0.0)))
            px=x+8+(w-16)*v
            d.rounded_rectangle((px-12,y+h*0.22,px+12,y+h*0.78),radius=6,fill=(0,199,194,255),outline=(220,250,248,255),width=2)
        elif typ in ("label","text"):
            if typ == "text": text=item.get("text","")
            elif item.get("kind")=="name": text=name(item.get("param",-1))
            else: text=display(item.get("param",-1))
            f=font(Path(item.get("style","")),item.get("size",24))
            color=rgba(item.get("color","fff4f8fa"))
            if item.get("uppercase"): text=text.upper()
            box=d.textbbox((0,0),text,font=f); tw=box[2]-box[0]
            align=item.get("align","left").lower()
            if "right" in align: tx=x+w-tw
            elif "center" in align: tx=x+(w-tw)/2
            else: tx=x
            if tw>w: overflow.append({"page":page["name"],"text":text,"width":round(tw,1),"available":w})
            # Clip to the exact label rectangle as a Force widget does.
            d.rectangle((x,y,x+w-1,y+h-1),fill=(0,0,0,0)) if False else None
            layer=Image.new("RGBA",canvas.size,(0,0,0,0)); ld=ImageDraw.Draw(layer)
            ld.text((round(tx),y),text,font=f,fill=color)
            mask=Image.new("L",canvas.size,0); md=ImageDraw.Draw(mask); md.rectangle((x,y,x+w-1,y+h-1),fill=255)
            canvas.alpha_composite(Image.composite(layer,Image.new("RGBA",canvas.size,(0,0,0,0)),mask))
            if tw>w:
                d.rectangle((x,y,x+w-1,y+h-1),outline=(255,77,55,255),width=2)
    if out_path:
        out_path.parent.mkdir(parents=True,exist_ok=True); canvas.convert("RGB").save(out_path)
    return canvas, overflow

def layout_report(model, values=None, display=None, name=None):
    values = values or {}
    display = display or (lambda _i: "")
    name = name or (lambda _i: "")
    report={"schema":"trollfx-force-simulator-layout-report-v1","renderer":"Pillow preview from generated SDK TUI.json, Q-Links.json and PNGs; stock Slider is approximate","canvas":[1280,628],"pages":[],"errors":[],"warnings":[]}
    for pi,page in enumerate(model["pages"]):
        for item in page["items"]:
            for k in ("x","y","w","h"):
                if not isinstance(item[k],(int,float)): report["errors"].append({"page":page["name"],"item":item,"issue":"non-numeric bounds"})
            if item["x"]<0 or item["y"]<0 or item["x"]+item["w"]>page["width"] or item["y"]+item["h"]>page["height"]:
                report["errors"].append({"page":page["name"],"item":item.get("name",item.get("parent")),"issue":"out of bounds"})
        labels=[x for x in page["items"] if x["type"] in ("label","text") and shown(x,values)]
        overflows=[]
        for item in labels:
            text=item.get("text","") if item["type"]=="text" else (name(item.get("param",-1)) if item.get("kind")=="name" else display(item.get("param",-1)))
            if item.get("uppercase"): text=text.upper()
            measured=ImageDraw.Draw(Image.new("RGB",(1,1))).textbbox((0,0),text,font=font(Path(item.get("style","")),item.get("size",24)))
            width=measured[2]-measured[0]
            if width>item["w"]: overflows.append({"text":text,"rendered_width_px":round(width,1),"available_width_px":item["w"],"overflow_px":round(width-item["w"],1)})
        if overflows: report["warnings"].append({"page":page["name"],"issue":"text clipped by widget bounds","items":overflows})
        collisions=[]
        for i,a in enumerate(labels):
            for b in labels[i+1:]:
                ix=max(0,min(a["x"]+a["w"],b["x"]+b["w"])-max(a["x"],b["x"]))
                iy=max(0,min(a["y"]+a["h"],b["y"]+b["h"])-max(a["y"],b["y"]))
                if ix>0 and iy>0 and a.get("parent")!=b.get("parent"):
                    collisions.append({"first":a.get("text") or a.get("parent"),"second":b.get("text") or b.get("parent"),"intersection_px":[round(ix,1),round(iy,1)]})
        if collisions: report["warnings"].append({"page":page["name"],"issue":"overlapping label widget bounds","pairs":collisions})
        texts=[x.get("text","") for x in labels if x.get("type")=="text"]
        duplicates=sorted(t for t in set(texts) if texts.count(t)>1 and t)
        if duplicates: report["warnings"].append({"page":page["name"],"issue":"duplicate text", "values":duplicates})
        fonts=sorted({x.get("font","")+"/"+x.get("style","") for x in labels})
        if len(fonts)>2: report["warnings"].append({"page":page["name"],"issue":"multiple label fonts","fonts":fonts})
        widgets=[x for x in page["items"] if x["type"] in ("film","slider","button")]
        report["pages"].append({"name":page["name"],"items":len(page["items"]),"touch_targets":len(page["hitzones"]),"qlink_map":page["qlinks"],"fonts":fonts,"native_slider_approximations":sum(x["type"]=="slider" for x in widgets)})
    report["errors"].extend(model.get("diagnostics",[]))
    return report
