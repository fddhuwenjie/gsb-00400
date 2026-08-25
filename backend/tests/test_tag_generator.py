from app.services.tag_generator import TagGenerator

tg = TagGenerator()

class TestTagGenerator:
    def test_generate_tags_basic(self):
        tags = tg.generate_tags("产品A-方案-v1.txt", "产品A 技术方案", "txt")
        names = [t["name"] for t in tags]
        assert "file_type" in names
        assert "year" in names

    def test_generate_tags_keyword_match(self):
        tags = tg.generate_tags("产品A-销售方案.pdf", "产品A 销售版本", "pdf")
        values = [t["value"] for t in tags]
        assert "产品A" in values
        assert "销售" in values

    def test_generate_standard_name(self):
        tags = [
            {"type": "semantic", "name": "产品", "value": "产品A"},
            {"type": "semantic", "name": "角色", "value": "技术"},
            {"type": "basic", "name": "year", "value": "2024"},
        ]
        name = tg.generate_standard_name("产品A-v2.txt", "", "方案", tags)
        assert "产品A" in name
        assert "solution" in name
        assert "技术" in name

    def test_suggest_bucket_video(self):
        assert tg.suggest_bucket("demo.mp4", "mp4") == "视频"

    def test_suggest_bucket_archive(self):
        assert tg.suggest_bucket("setup.zip", "zip") == "安装包"

    def test_suggest_bucket_solution(self):
        assert tg.suggest_bucket("产品A-解决方案.pdf", "pdf") == "方案"

    def test_suggest_bucket_brochure(self):
        assert tg.suggest_bucket("产品B-彩页-宣传.pdf", "pdf") == "彩页"

    def test_extract_year(self):
        assert TagGenerator.extract_year("文档-2024年") == "2024"

    def test_extract_version(self):
        assert TagGenerator.extract_version("产品-v2.1-文档") == "v2.1"

    def test_doc_key_same_business_document(self):
        k1 = TagGenerator.doc_key("产品A-安装说明-技术标准-v1-2023.pdf")
        k2 = TagGenerator.doc_key("产品A-安装说明-技术标准-v2-2024.pdf")
        assert k1 == k2 == "产品a-安装说明-技术标准"

    def test_doc_key_strips_version_and_year_only(self):
        key = TagGenerator.doc_key("spec-v2.1-2024.txt")
        assert key == "spec"
        assert "v2" not in key and "2024" not in key

    def test_doc_key_different_documents_differ(self):
        k1 = TagGenerator.doc_key("产品A-解决方案-v1.txt")
        k2 = TagGenerator.doc_key("产品B-解决方案-v1.txt")
        assert k1 != k2

    def test_doc_key_repeated_upload_same_name(self):
        assert TagGenerator.doc_key("spec.txt") == TagGenerator.doc_key("spec.txt")

    def test_detect_relations(self):
        file_tags = {
            1: [{"value": "产品A"}, {"value": "技术"}, {"value": "2024"}],
            2: [{"value": "产品A"}, {"value": "技术"}, {"value": "2023"}],
            3: [{"value": "产品B"}, {"value": "销售"}],
        }
        relations = tg.detect_relations(file_tags)
        assert len(relations) >= 1
        assert relations[0][0] == 1 and relations[0][1] == 2
