"""Independent finite byte/header tests. No socket, SQL, auth or service."""
import json
import os
from pathlib import Path
import unittest

from uta.private_stream_codec import EncodeReject,OutboundBuffer,WireFrame


class MutableHeaderReferenceTests(unittest.TestCase):
    observations=[]

    @classmethod
    def tearDownClass(cls):
        if os.environ.get('UTA_CODEC_PEER_OBSERVATIONS'):
            Path(os.environ['UTA_CODEC_PEER_OBSERVATIONS']).write_text(json.dumps(cls.observations,indent=2)+'\n')

    def observe(self,kind):
        original=b'\x81\x01x'
        header=bytearray(b'\x81\x01')
        supplied=header if kind=='bytearray' else memoryview(header)
        try:frame=WireFrame(1,supplied,b'x')
        except EncodeReject as error:
            value={'kind':kind,'constructor_rejected':True,'code':error.code}
            self.observations.append(value);return value
        queue=OutboundBuffer();queue.enqueue_application(frame,now_ms=0)
        before=queue.application_wire_bytes
        header[0]=0x82
        if kind=='bytearray':header.extend(b'yz')
        changed=bytes(frame.header)+bytes(frame.payload)
        actual=bytearray()
        for _ in range(8):
            chunk=queue.peek(now_ms=1)
            if chunk is None:break
            actual.extend(chunk.data)
            queue.advance(chunk,len(chunk.data),now_ms=1)
        value={'kind':kind,'constructor_rejected':False,'original_expected_wire_hex':original.hex(),'changed_wire_hex':changed.hex(),'sent_wire_hex':bytes(actual).hex(),'original_accounted_wire_bytes':before,'actual_mutated_wire_size':frame.wire_size,'after_release_accounted_wire_bytes':queue.application_wire_bytes}
        self.observations.append(value);return value

    def test_bytearray_header_does_not_change_published_wire(self):
        value=self.observe('bytearray')
        if value['constructor_rejected']:return
        self.assertEqual(value['sent_wire_hex'],'810178')

    def test_bytearray_header_does_not_make_release_accounting_negative(self):
        value=self.observe('bytearray')
        if value['constructor_rejected']:return
        self.assertEqual(value['after_release_accounted_wire_bytes'],0)

    def test_memoryview_header_cannot_change_controlled_frame_opcode(self):
        value=self.observe('memoryview')
        if value['constructor_rejected']:return
        self.assertEqual(value['sent_wire_hex'],'810178')


if __name__=='__main__':unittest.main()
