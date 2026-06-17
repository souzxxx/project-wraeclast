import base64
import zlib

import pytest

from collector.pob_parser import PoBParseError, decode_pob_code, parse_pob_code

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PathOfBuilding>
  <Build level="92" className="Witch" ascendClassName="Infernalist"/>
  <Skills>
    <SkillSet>
      <Skill>
        <Gem nameSpec="Fireball" level="20" quality="20" enabled="true"/>
        <Gem nameSpec="Spell Echo" level="18" quality="0" enabled="true"/>
      </Skill>
    </SkillSet>
  </Skills>
  <Items>
    <Item>Rarity: RARE
Doom Shard
Vaal Regalia</Item>
  </Items>
</PathOfBuilding>"""


def make_pob_code(xml: str) -> str:
    return base64.urlsafe_b64encode(zlib.compress(xml.encode("utf-8"))).decode("ascii")


def test_decode_roundtrip():
    code = make_pob_code(SAMPLE_XML)
    assert "PathOfBuilding" in decode_pob_code(code)


def test_parse_extracts_core_fields():
    snap = parse_pob_code(make_pob_code(SAMPLE_XML), character_name="MyWitch")
    assert snap.character_name == "MyWitch"
    assert snap.char_class == "Witch"
    assert snap.level == 92
    assert snap.gear["ascendancy"] == "Infernalist"


def test_parse_extracts_gems():
    snap = parse_pob_code(make_pob_code(SAMPLE_XML))
    names = {g["name"] for g in snap.gems}
    assert names == {"Fireball", "Spell Echo"}
    fireball = next(g for g in snap.gems if g["name"] == "Fireball")
    assert fireball["level"] == 20
    assert fireball["quality"] == 20


def test_parse_extracts_items():
    snap = parse_pob_code(make_pob_code(SAMPLE_XML))
    items = snap.gear["items"]
    assert items[0]["name"] == "Doom Shard"


def test_bad_code_raises():
    with pytest.raises(PoBParseError):
        decode_pob_code("not-a-real-pob-code!!!")
    with pytest.raises(PoBParseError):
        decode_pob_code("")
