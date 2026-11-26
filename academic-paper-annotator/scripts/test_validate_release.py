#!/usr/bin/env python3
"""Regression tests using authored toy content; no paper or network needed."""
import hashlib,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from validate_release import check_release

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.p=Path(self.temp.name)
        self.html='<html><body><a href="#R1">ref</a><article id="P001" class="unit"><p class="original">In this toy example, 3 of 4 items match.</p><div class="translation">在此虚构示例中，4 项中有 3 项匹配。</div><details class="annotation">结果：给出虚构示例</details></article><p id="R1">Authored source.</p><p id="C001">Toy claim.</p></body></html>'
        self.units=[{'id':'P001','unit_type':'body','original_text':'In this toy example, 3 of 4 items match.','translation_zh':'在此虚构示例中，4 项中有 3 项匹配。','logical_role':'给出虚构示例','rhetorical_function':'结果','status':{'translation':'done','annotation':'brief','extraction':'verified','source_check':'sampled'},'highlights':[]}]
        self.base={'required_unit_ids':['P001'],'unit_counts':{'body':1},'figure_count':0,'table_count':0,'reference_ids':['R1']}
    def write(self,name,obj):
        p=self.p/name;p.write_text(json.dumps(obj,ensure_ascii=False));return p
    def run_check(self,html=None,units=None,stale=False,tables=None,figures=None,include_analysis=True,analysis=None):
        html=self.html if html is None else html;hp=self.p/'final.html';hp.write_text(html)
        review={'file_sha256':hashlib.sha256((self.html if stale else html).encode()).hexdigest(),'content_review':{'status':'passed'},'browser_review':{'status':'blocked','reason':'Toy fixture has no renderer.','plan':'Inspect in an allowed local browser.'}}
        return check_release(hp,self.write('u.json',self.units if units is None else units),self.write('b.json',self.base),tables_path=self.write('t.json',tables) if tables is not None else None,figures_path=self.write('f.json',figures) if figures is not None else None,analysis_path=self.write('a.json',analysis if analysis is not None else {'claims':[{'id':'C001','units':['P001'],'quote':'3 of 4'}]}) if include_analysis else None,review_path=self.write('r.json',review))
    def test_complete_with_real_limit(self):self.assertEqual(self.run_check()['verdict'],'ready_with_verification_limits')
    def test_missing_translation_blocks(self):
        self.units[0]['translation_zh']='';self.units[0]['status']['translation']='missing'
        r=self.run_check();self.assertEqual(r['verdict'],'checkpoint');self.assertFalse(r['checks']['P001:translation_done'])
    def test_changed_original_blocks(self):
        r=self.run_check(html=self.html.replace('3 of 4','4 of 4'));self.assertFalse(r['checks']['P001:original_exact'])
    def test_wrong_translation_number_blocks(self):
        self.units[0]['translation_zh']='在此虚构示例中，4 项中有 2 项匹配。'
        altered=self.html.replace('4 项中有 3 项','4 项中有 2 项')
        self.assertFalse(self.run_check(html=altered)['checks']['P001:numeric_literals_present'])
    def test_missing_rendered_annotation_blocks(self):
        broken=self.html.replace('<details class="annotation">结果：给出虚构示例</details>','')
        self.assertFalse(self.run_check(html=broken)['checks']['P001:annotation_rendered'])
    def test_relative_css_resource_blocks(self):
        self.assertFalse(self.run_check(html=self.html.replace('<body>','<style>body{background:url(secret.png)}</style><body>'))['checks']['no_external_runtime_resources'])
    def test_documented_role_object_supported(self):
        self.units[0]['rhetorical_function']={'primary':'结果','secondary':[]}
        self.assertEqual(self.run_check()['verdict'],'ready_with_verification_limits')
    def test_uppercase_css_import_blocks(self):
        broken=self.html.replace('<body>','<style>@IMPORT "https://example.invalid/a.css";</style><body>')
        self.assertFalse(self.run_check(html=broken)['checks']['no_external_runtime_resources'])
    def test_empty_image_source_blocks(self):
        self.assertFalse(self.run_check(html=self.html.replace('</body>','<img src=""></body>'))['checks']['all_images_embedded_nonempty'])
    def test_analysis_omission_blocks(self):self.assertFalse(self.run_check(include_analysis=False)['checks']['analysis_data_provided'])
    def test_missing_figure_image_blocks(self):
        self.base['figure_count']=1
        figure={'id':'F001','original_text':'Authored figure.','translation_zh':'自编图。'}
        html=self.html.replace('</body>','<figure id="F001"><p class="original">Authored figure.</p><div class="translation">自编图。</div></figure></body>')
        self.assertFalse(self.run_check(html=html,figures=[figure])['checks']['figure_images_present'])
    def test_reordered_unit_blocks(self):
        second=dict(self.units[0]);second['id']='P002';self.units.append(second);self.base['required_unit_ids'].append('P002');self.base['unit_counts']['body']=2
        article=self.html.split('<article',1)[1].split('</article>',1)[0];second_html='<article'+article.replace('id="P001"','id="P002"')+'</article>'
        broken=self.html.replace('<article id="P001" class="unit">',second_html+'<article id="P001" class="unit">')
        self.assertFalse(self.run_check(html=broken)['checks']['rendered_unit_order'])
    def test_missing_reference_blocks(self):self.assertFalse(self.run_check(html=self.html.replace('id="R1"','id="R2"'))['checks']['internal_anchor_targets'])
    def test_old_review_hash_blocks(self):self.assertFalse(self.run_check(html=self.html.replace('</body>','<p>changed</p></body>'),stale=True)['checks']['review_matches_final_sha256'])
    def test_wrong_table_cell_blocks(self):
        self.base['table_count']=1
        r=self.run_check(html=self.html.replace('</body>','<table id="T001"><tr><td><span class="cell-original">42</span></td></tr></table></body>'),tables=[{'id':'T001','rows':[['24']]}]);self.assertFalse(r['checks']['all_source_table_cells_exact'])
    def test_missing_baseline_unit_blocks(self):
        self.base['required_unit_ids'].append('P002');self.assertFalse(self.run_check()['checks']['baseline_required_units'])
    def test_omitted_rendered_highlight_blocks(self):
        self.units[0]['highlights']=[{'quote':'3 of 4','category':'evidence'}]
        self.assertFalse(self.run_check()['checks']['P001:highlights_rendered'])
    def test_extraction_failed_blocks(self):
        self.units[0]['status']['extraction']='failed'
        self.assertFalse(self.run_check()['checks']['P001:extraction_verified'])
    def test_missing_source_check_blocks(self):
        self.units[0]['status'].pop('source_check')
        self.assertFalse(self.run_check()['checks']['P001:source_check_recorded'])
    def test_unknown_cross_reference_blocks(self):
        self.units[0]['cross_references']=['P404']
        self.assertFalse(self.run_check()['checks']['P001:cross_reference_targets'])
    def test_empty_reference_blocks(self):
        self.assertFalse(self.run_check(html=self.html.replace('Authored source.',''))['checks']['references_nonempty'])
    def test_undeclared_source_blocks(self):
        extra='<article class="unit" id="P999"><p class="original">Invented source.</p></article>'
        self.assertFalse(self.run_check(html=self.html.replace('</body>',extra+'</body>'))['checks']['rendered_scope_exact'])
    def test_table_boundaries_block(self):
        self.base['table_count']=1
        table='<table id="T001"><tr>'+''.join('<td><span class="cell-original">'+x+'</span></td>' for x in 'ABCD')+'</tr></table>'
        self.assertFalse(self.run_check(html=self.html.replace('</body>',table+'</body>'),tables=[{'id':'T001','rows':[['A','B'],['C','D']]}])['checks']['all_source_table_cells_exact'])
    def test_empty_image_payload_blocks(self):
        bad='<img src="data:image/png;base64,">'
        self.assertFalse(self.run_check(html=self.html.replace('</body>',bad+'</body>'))['checks']['embedded_image_encoding'])
    def test_wrong_root_overwrites_old_success(self):
        hp=self.p/'final.html';hp.write_text(self.html)
        up=self.write('bad.json',{'wrong':'root'});bp=self.write('base.json',self.base);report=self.write('report.json',{'verdict':'ready'})
        cmd=[sys.executable,str(Path(__file__).with_name('validate_release.py')),'--html',str(hp),'--units',str(up),'--baseline',str(bp),'--report',str(report)]
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertNotIn('Traceback',result.stderr);self.assertEqual(json.loads(report.read_text())['verdict'],'not_auditable')
    def test_nullable_role_rejected_cleanly(self):
        from validate_release import DataError
        self.units[0]['rhetorical_function']={'primary':'结果','secondary':None}
        with self.assertRaises(DataError):self.run_check()
    def test_percent_encoded_fragment_supported(self):
        changed=self.html.replace('href="#R1"','href="#%52%31"')
        self.assertTrue(self.run_check(html=changed)['checks']['internal_anchor_targets'])
    def test_unknown_secondary_claim_source_blocks(self):
        data={'claims':[{'id':'C001','units':['P001','P404'],'quote':'3 of 4'}]}
        self.assertFalse(self.run_check(analysis=data)['checks']['claim_source_targets'])
    def test_duplicate_claim_ids_block(self):
        claim={'id':'C001','units':['P001'],'quote':'3 of 4'}
        self.assertFalse(self.run_check(analysis={'claims':[claim,claim]})['checks']['claim_ids_unique_and_rendered'])
    def test_missing_table_id_blocks(self):
        self.base['table_count']=1
        table='<table><tr><td><span class="cell-original">A</span></td></tr></table>'
        self.assertFalse(self.run_check(html=self.html.replace('</body>',table+'</body>'),tables=[{'id':'T001','rows':[['A']]}])['checks']['table_ids_present'])
    def test_ambiguous_highlight_blocks(self):
        self.units[0]['highlights']=[{'quote':'not present','category':'evidence'}]
        self.assertFalse(self.run_check()['checks']['P001:highlights_exact_unique'])
if __name__=='__main__':unittest.main()
