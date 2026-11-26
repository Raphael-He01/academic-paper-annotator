import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'academic-paper-annotator/scripts'
sys.path.insert(0, str(SCRIPTS))
from build_workbench import build
from validate_release import check_release


class WorkbenchBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'data'
        shutil.copytree(ROOT / 'examples/synthetic', self.data)

    def test_rebuild_is_byte_identical_and_does_not_change_review(self):
        before = (self.data / 'review.json').read_bytes()
        output = self.data / 'rebuilt.html'
        build(self.data, output)
        self.assertEqual(output.read_bytes(), (self.data / 'index.html').read_bytes())
        self.assertEqual(before, (self.data / 'review.json').read_bytes())
        report = check_release(output, self.data/'units.json', self.data/'baseline.json', self.data/'figures.json', self.data/'tables.json', self.data/'analysis.json', self.data/'review.json')
        self.assertEqual(report['verdict'], 'ready_with_verification_limits')
        self.assertTrue(all(report['checks'].values()))

    def test_untrusted_original_text_is_escaped(self):
        units = json.loads((self.data/'units.json').read_text(encoding='utf-8'))
        units[0]['original_text'] += '<script>alert("untrusted")</script>'
        (self.data/'units.json').write_text(json.dumps(units,ensure_ascii=False),encoding='utf-8')
        output=self.data/'escaped.html';build(self.data,output)
        html=output.read_text(encoding='utf-8')
        self.assertNotIn('<script>alert("untrusted")</script>',html)
        self.assertIn('&lt;script&gt;alert(',html)
        self.assertNotEqual(hashlib.sha256(output.read_bytes()).hexdigest(),json.loads((self.data/'review.json').read_text())['file_sha256'])

    def test_image_path_cannot_read_outside_data_directory(self):
        figures=json.loads((self.data/'figures.json').read_text())
        figures[0]['image_path']='../outside.svg'
        (self.data/'figures.json').write_text(json.dumps(figures))
        with self.assertRaises(ValueError):build(self.data,self.data/'out.html')

    def test_repeated_heading_does_not_reorder_source(self):
        units=json.loads((self.data/'units.json').read_text())
        for i,u in enumerate(units):u['section']='Repeated' if i in (0,2) else 'Other'+str(i)
        (self.data/'units.json').write_text(json.dumps(units))
        out=self.data/'order.html';build(self.data,out);content=out.read_text()
        positions=[content.index('class="unit" id="'+u['id']+'"') for u in units]
        self.assertEqual(positions,sorted(positions))

    def test_source_location_text_is_preserved_and_escaped(self):
        units=json.loads((self.data/'units.json').read_text());units[0]['source_location']={'file':'unique-source-paper.pdf','pdf_page':17,'print_page':'S42','note':'<source>'}
        (self.data/'units.json').write_text(json.dumps(units))
        out=self.data/'located.html';build(self.data,out);content=out.read_text()
        self.assertIn('unique-source-paper.pdf',content);self.assertIn('S42',content);self.assertIn('&lt;source&gt;',content)

    def test_invalid_analysis_has_controlled_cli_failure(self):
        import subprocess
        (self.data/'analysis.json').write_text('[]')
        p=subprocess.run([sys.executable,str(SCRIPTS/'build_workbench.py'),'--data',str(self.data),'--output',str(self.data/'bad.html')],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertNotIn('Traceback',p.stderr);self.assertFalse((self.data/'bad.html').exists())

    def test_authored_csv_reproduces_published_counts(self):
        with (self.data/'reports.csv').open(encoding='utf-8',newline='') as source:
            rows=list(csv.DictReader(source))
        self.assertEqual(len(rows),200)
        self.assertEqual(sum(int(r['has_error']) for r in rows),40)
        for key,expected in [('rule_a_flag',(26,8)),('rule_b_flag',(35,15))]:
            actual=(sum(int(r[key]) for r in rows if r['has_error']=='1'),sum(int(r[key]) for r in rows if r['has_error']=='0'))
            self.assertEqual(actual,expected)

if __name__ == '__main__':unittest.main()
