# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Require UAC before SetupLdr touches TEMP, without moving its archive."""
import hashlib
import mmap
from pathlib import Path
import xml.etree.ElementTree as ET
import pefile


def require_admin(path):
    path=Path(path)
    pe=pefile.PE(str(path))
    resource=next(item for item in pe.DIRECTORY_ENTRY_RESOURCE.entries if item.id==24).directory.entries[0].directory.entries[0].data.struct
    offset=pe.get_offset_from_rva(resource.OffsetToData)
    original=pe.get_data(resource.OffsetToData,resource.Size)
    assert pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size==0,'Patch the manifest before signing'
    overlay=pe.get_overlay_data_start_offset()
    pe.close()
    before=path.read_bytes()
    token=b'level="asInvoker"'
    assert original.count(token)==1
    replacement=b'level="requireAdministrator"'
    extra=len(replacement)-len(token)
    # Inno reserves spaces immediately after the privilege attribute.
    needle=token+b' '*(extra+1)
    assert needle in original,'Missing reserved manifest padding'
    updated=original.replace(needle,replacement+b' ',1)
    assert len(updated)==len(original)
    parsed=ET.fromstring(updated)
    level=next(node for node in parsed.iter() if node.tag.endswith('requestedExecutionLevel'))
    assert level.attrib==dict(level='requireAdministrator',uiAccess='false')
    with path.open('r+b') as stream,mmap.mmap(stream.fileno(),0) as data:
        data[offset:offset+len(updated)]=updated
    after=path.read_bytes()
    assert before[:offset]==after[:offset] and before[offset+len(original):]==after[offset+len(original):]
    assert len(before)==len(after)
    assert before[overlay:]==after[overlay:]
    return dict(level='requireAdministrator',archive_unchanged=True,bytes=len(after),
                archive_sha256=hashlib.sha256(after[overlay:]).hexdigest())
