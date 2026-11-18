"""Pure literal checkout-step checks; SOURCE elsewhere cannot mask bad ref."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checkout_ref_controller',ROOT/'tools/independent_m0_controller.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def checked_workload_ref(text):
    # This deliberately accepts only our pinned, literal workflow layout.
    blocks=re.split(r'(?m)^      - ',text)[1:]
    selected=[block for block in blocks if re.search(r'(?m)^          path: workload$',block)]
    if len(selected)!=1:raise ValueError('one literal workload checkout required')
    block=selected[0]
    if not re.search(r'(?m)^        uses: actions/checkout@[0-9a-f]{40}$',block):raise ValueError('pinned checkout action required')
    refs=re.findall(r'(?m)^          ref: (.*)$',block)
    if len(refs)!=1 or re.fullmatch('[0-9a-f]{40}',refs[0]) is None or refs[0]!=m.SOURCE:
        raise ValueError('workload checkout ref must equal exact SOURCE')
    return refs[0]

class CheckoutRefContract(unittest.TestCase):
    def workflows(self):
        return [(ROOT/'.github/workflows'/name).read_text() for name in ('independent-m0-once.yml','independent-m0.yml')]
    def test_each_actual_workload_checkout_is_exact_source40(self):
        for text in self.workflows():
            with self.subTest(workflow=text.splitlines()[0]):self.assertEqual(checked_workload_ref(text),m.SOURCE)
    def test_once_only_ref_mutation_fails_even_unchanged_source_assert_passes(self):
        text=self.workflows()[0]
        # Normalize the actual target for this negative control so the first
        # pre-fix test above still retains the real sealed workflow failure.
        text=re.sub(r'(?m)^          ref: [0-9a-f]+(?=\n          path: workload$)',lambda _: '          ref: '+m.SOURCE,text)
        for wrong in ('f'*40,'909acecd153e2e89dfe2238e3ed3a3d3c9f0'):
            changed=text.replace('          ref: '+m.SOURCE+'\n          path: workload','          ref: '+wrong+'\n          path: workload',1)
            self.assertIn("assert value['source_commit'] == '"+m.SOURCE+"'",changed)
            self.assertIn(m.SOURCE,changed)
            with self.assertRaises(ValueError):checked_workload_ref(changed)
    def test_dispatch_ref_mutation_is_rejected(self):
        text=self.workflows()[1]
        changed=text.replace('          ref: '+m.SOURCE+'\n          path: workload','          ref: '+'f'*40+'\n          path: workload',1)
        with self.assertRaises(ValueError):checked_workload_ref(changed)
    def test_multiple_or_missing_workload_step_is_rejected(self):
        text=self.workflows()[1]
        for changed in (text.replace('          path: workload','          path: unrelated'),text+text):
            with self.assertRaises(ValueError):checked_workload_ref(changed)

if __name__=='__main__':unittest.main()
