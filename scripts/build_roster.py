"""从浙江省委组织部公开附件重建 2026 院校名单；不根据社区名单推断资格。"""
from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENT = 'https://xds.ecnu.edu.cn/68/b9/c51123a747705/page.psp'
BASE = 'https://xds.ecnu.edu.cn/_upload/article/files/22/1e/62aa2a224e2492364d292ceb6f20/'
REGULAR = BASE + '18c2ab3a-6e32-4a82-a1f7-580e247c8065.doc'
SHORTAGE = BASE + '532fa022-470d-48a8-bcfc-1cf1768e67ac.xlsx'

# id | 学校 | 省份 | 官方域名 | 研究生招生入口；后续单位盘点单独维护。
METADATA = '''thu|清华大学|北京|www.tsinghua.edu.cn|yz.tsinghua.edu.cn
pku|北京大学|北京|www.pku.edu.cn|admission.pku.edu.cn
ruc|中国人民大学|北京|www.ruc.edu.cn|pgs.ruc.edu.cn
buaa|北京航空航天大学|北京|www.buaa.edu.cn|yzb.buaa.edu.cn
bit|北京理工大学|北京|www.bit.edu.cn|grd.bit.edu.cn
cau|中国农业大学|北京|www.cau.edu.cn|yz.cau.edu.cn
bnu|北京师范大学|北京|www.bnu.edu.cn|yz.bnu.edu.cn
muc|中央民族大学|北京|www.muc.edu.cn|grs.muc.edu.cn
nankai|南开大学|天津|www.nankai.edu.cn|yzb.nankai.edu.cn
tju|天津大学|天津|www.tju.edu.cn|yzb.tju.edu.cn
dlut|大连理工大学|辽宁|www.dlut.edu.cn|gs.dlut.edu.cn
jlu|吉林大学|吉林|www.jlu.edu.cn|zsb.jlu.edu.cn
hit|哈尔滨工业大学|黑龙江|www.hit.edu.cn|yzb.hit.edu.cn
fudan|复旦大学|上海|www.fudan.edu.cn|gsao.fudan.edu.cn
tongji|同济大学|上海|www.tongji.edu.cn|yz.tongji.edu.cn
sjtu|上海交通大学|上海|www.sjtu.edu.cn|yzb.sjtu.edu.cn
ecnu|华东师范大学|上海|www.ecnu.edu.cn|yjszs.ecnu.edu.cn
nju|南京大学|江苏|www.nju.edu.cn|yzb.nju.edu.cn
seu|东南大学|江苏|www.seu.edu.cn|yzb.seu.edu.cn
zju|浙江大学|浙江|www.zju.edu.cn|grs.zju.edu.cn
ustc|中国科学技术大学|安徽|www.ustc.edu.cn|yz.ustc.edu.cn
xmu|厦门大学|福建|www.xmu.edu.cn|zs.xmu.edu.cn
sdu|山东大学|山东|www.sdu.edu.cn|www.yz.sdu.edu.cn
ouc|中国海洋大学|山东|www.ouc.edu.cn|yz.ouc.edu.cn
whu|武汉大学|湖北|www.whu.edu.cn|yz.whu.edu.cn
hust|华中科技大学|湖北|www.hust.edu.cn|gszs.hust.edu.cn
csu|中南大学|湖南|www.csu.edu.cn|gra.csu.edu.cn
sysu|中山大学|广东|www.sysu.edu.cn|graduate.sysu.edu.cn
scut|华南理工大学|广东|www.scut.edu.cn|yz.scut.edu.cn
scu|四川大学|四川|www.scu.edu.cn|yz.scu.edu.cn
uestc|电子科技大学|四川|www.uestc.edu.cn|yz.uestc.edu.cn
cqu|重庆大学|重庆|www.cqu.edu.cn|yz.cqu.edu.cn
xjtu|西安交通大学|陕西|www.xjtu.edu.cn|yz.xjtu.edu.cn
nwpu|西北工业大学|陕西|www.nwpu.edu.cn|yzb.nwpu.edu.cn
lzu|兰州大学|甘肃|www.lzu.edu.cn|yz.lzu.edu.cn
nudt|国防科技大学|湖南|www.nudt.edu.cn|yjszs.nudt.edu.cn
ucas|中国科学院大学|北京|www.ucas.ac.cn|admission.ucas.ac.cn
ucass|中国社会科学院大学|北京|www.ucass.edu.cn|skdzs.ucass.edu.cn
westlake|西湖大学|浙江|www.westlake.edu.cn|graduate.westlake.edu.cn
caa|中国美术学院|浙江|www.caa.edu.cn|grs.caa.edu.cn
zjut|浙江工业大学|浙江|www.zjut.edu.cn|www.yz.zjut.edu.cn
zjnu|浙江师范大学|浙江|www.zjnu.edu.cn|yzw.zjnu.edu.cn
nbu|宁波大学|浙江|www.nbu.edu.cn|graduate.nbu.edu.cn
zstu|浙江理工大学|浙江|www.zstu.edu.cn|gradadmission.zstu.edu.cn
hdu|杭州电子科技大学|浙江|www.hdu.edu.cn|grs.hdu.edu.cn
zjgsu|浙江工商大学|浙江|www.zjgsu.edu.cn|yjszs.zjgsu.edu.cn
cjlu|中国计量大学|浙江|www.cjlu.edu.cn|yjsb.cjlu.edu.cn
zcmu|浙江中医药大学|浙江|www.zcmu.edu.cn|yjsgl.zcmu.edu.cn
zjou|浙江海洋大学|浙江|www.zjou.edu.cn|yjs.zjou.edu.cn
zafu|浙江农林大学|浙江|www.zafu.edu.cn|yjszs.zafu.edu.cn
wmu|温州医科大学|浙江|www.wmu.edu.cn|yjsy.wmu.edu.cn
zufe|浙江财经大学|浙江|www.zufe.edu.cn|yjsc.zufe.edu.cn
hznu|杭州师范大学|浙江|www.hznu.edu.cn|yjs.hznu.edu.cn
wzu|温州大学|浙江|www.wzu.edu.cn|yjsb.wzu.edu.cn
cupl|中国政法大学|北京|www.cupl.edu.cn|yjsy.cupl.edu.cn
swupl|西南政法大学|重庆|www.swupl.edu.cn|yjsy.swupl.edu.cn
ecupl|华东政法大学|上海|www.ecupl.edu.cn|yjsy.ecupl.edu.cn
zuel|中南财经政法大学|湖北|www.zuel.edu.cn|yjsy.zuel.edu.cn
nwupl|西北政法大学|陕西|www.nwupl.edu.cn|grs.nwupl.edu.cn
cufe|中央财经大学|北京|www.cufe.edu.cn|gs.cufe.edu.cn
ccps|中共中央党校（国家行政学院）|北京|www.ccps.gov.cn|www.ccps.gov.cn
nenu|东北师范大学|吉林|www.nenu.edu.cn|yjsy.nenu.edu.cn
njnu|南京师范大学|江苏|www.nnu.edu.cn|yz.njnu.edu.cn
xtu|湘潭大学|湖南|www.xtu.edu.cn|yjsc.xtu.edu.cn
sdnu|山东师范大学|山东|www.sdnu.edu.cn|www.yjszs.sdnu.edu.cn
xidian|西安电子科技大学|陕西|www.xidian.edu.cn|gr.xidian.edu.cn
hhu|河海大学|江苏|www.hhu.edu.cn|gs.hhu.edu.cn
njmu|南京医科大学|江苏|www.njmu.edu.cn|yjszs.njmu.edu.cn'''


def build() -> None:
    """名单划分与专业限制由附件原始单元格生成。"""
    doc = urlopen(REGULAR, timeout=40).read().decode('utf-16le', errors='ignore')
    archive = ZipFile(io.BytesIO(urlopen(SHORTAGE, timeout=40).read()))
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    strings = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
    shared = [''.join(x.itertext()) for x in strings.findall('s:si', ns)]
    worksheet = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    rows = []
    for row in worksheet.findall('s:sheetData/s:row', ns):
        values = []
        for cell in row.findall('s:c', ns):
            value = cell.find('s:v', ns)
            if value is None:
                values.append(None)
            else:
                values.append(shared[int(value.text)] if cell.get('t') == 's' else value.text)
        if len(values) == 4 and values[0] and str(values[0]).isdigit():
            rows.append(values)
    restrictions: dict[str, list[str]] = {}
    for row in rows:
        _, code, discipline, raw_names = row
        for name in str(raw_names).split('\n')[0].split('、'):
            restrictions.setdefault(name, []).append(f'{code} {discipline}')
    schools = []
    lines = METADATA.splitlines()
    for index, line in enumerate(lines):
        identifier, name, province, domain, graduate = line.split('|')
        if index < 59 and name not in doc:
            raise ValueError(f'常规附件未找到 {name}')
        if index >= 59 and name not in restrictions:
            raise ValueError(f'紧缺专业附件未找到 {name}')
        groups = []
        if index < 39:
            groups.append('常规·省市及县乡')
        elif index < 54:
            groups.append('常规·浙江省内重点本科')
        elif index < 59:
            groups.append('常规·政法专项')
        if name in restrictions:
            groups.append('定向紧缺专业')
        note = '学校入选不代表所有专业和学历层次均符合职位条件，需结合具体职位表核对。'
        if 39 <= index < 54:
            note += '常规选调以县乡机关为主；部分市直职位同时面向本组，另有专门资格条件。'
        if 54 <= index < 59:
            note += '常规范围仅限公告列明的纪检监察、公检法司等要求法律专业背景职位。'
        if index >= 59:
            note += '本校仅因指定紧缺专业纳入；页面计算相关学院不当然符合该专业范围。'
        if name == '中国科学院大学':
            note += '研究所培养单位须核对实际学籍、毕业证及选调职位要求。'
        schools.append(dict(id=identifier, name=name, province=province, groups=groups,
                            rosterYear=2026, rosterSources=[ANNOUNCEMENT] + ([REGULAR] if index < 59 else []) + ([SHORTAGE] if name in restrictions else []),
                            eligibilityNote=note, disciplineRestrictions=restrictions.get(name, []),
                            homepage='https://' + domain + '/', inventoryStatus='pending',
                            inventoryNote='官方名单已核对；相关硕士培养单位、招生目录和当季公告仍需逐项盘点。'))
    assert len(schools) == 68
    assert sum('定向紧缺专业' in s['groups'] for s in schools) == 46
    out = ROOT / 'data' / 'schools.json'
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        previous = {s['id']: s for s in json.loads(out.read_text(encoding='utf-8'))}
        for school in schools:
            for key in ['inventoryStatus', 'inventoryNote']:
                school[key] = previous.get(school['id'], {}).get(key, school[key])
    out.write_text(json.dumps(schools, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(schools)} schools; 59 regular; 46 shortage; 68 unique')


if __name__ == '__main__':
    build()
