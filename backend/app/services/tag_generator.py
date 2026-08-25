import re
from typing import List, Dict, Tuple
from datetime import datetime

class TagGenerator:
    """标签与标准名生成服务"""
    
    BUCKETS = {"方案": "solution", "彩页": "brochure", "视频": "video", "安装包": "installer"}
    FILE_TYPES = {"pdf": "文档", "docx": "文档", "pptx": "演示", "mp4": "视频", "avi": "视频", "zip": "压缩包", "rar": "压缩包", "exe": "安装包"}
    
    KEYWORDS = {
        "产品": ["产品A", "产品B", "产品C", "系统", "平台", "软件"],
        "角色": ["销售", "技术", "客户", "内部", "对外"],
        "行业": ["金融", "医疗", "教育", "制造", "零售", "政府"],
        "场景": ["部署", "安装", "配置", "使用", "培训", "演示"]
    }
    
    @staticmethod
    def extract_year(text: str) -> str:
        """提取年份"""
        match = re.search(r'20[12]\d', text)
        return match.group() if match else str(datetime.now().year)
    
    @staticmethod
    def extract_version(text: str) -> str:
        """提取版本号"""
        match = re.search(r'[vV]?(\d+\.?\d*)', text)
        return f"v{match.group(1)}" if match else "v1"

    def generate_tags(self, filename: str, content: str, file_type: str) -> List[Dict]:
        """生成标签"""
        tags = []
        combined = f"{filename} {content[:2000]}"
        
        # 基础标签
        tags.append({"type": "basic", "name": "file_type", "value": self.FILE_TYPES.get(file_type.lower(), "其他")})
        tags.append({"type": "basic", "name": "year", "value": self.extract_year(combined)})
        
        # 关键词标签
        for category, keywords in self.KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    tags.append({"type": "semantic", "name": category, "value": kw})
        
        # 状态标签
        if any(w in combined.lower() for w in ["最新", "latest", "final", "正式"]):
            tags.append({"type": "status", "name": "is_latest", "value": "true"})
        if any(w in combined.lower() for w in ["推荐", "recommend", "标准"]):
            tags.append({"type": "status", "name": "is_recommended", "value": "true"})
        
        return tags
    
    def generate_standard_name(self, filename: str, content: str, bucket: str, tags: List[Dict]) -> str:
        """生成标准名"""
        product = next((t["value"] for t in tags if t["name"] == "产品"), "通用")
        role = next((t["value"] for t in tags if t["name"] == "角色"), "通用")
        year = next((t["value"] for t in tags if t["name"] == "year"), str(datetime.now().year))
        version = self.extract_version(filename)
        
        content_type = self.BUCKETS.get(bucket, bucket)
        return f"{product}-{content_type}-{role}版-{version}-{year}"
    
    def suggest_bucket(self, filename: str, file_type: str, content: str = "") -> str:
        """推荐分类桶"""
        combined = f"{filename} {content[:500]}".lower()
        
        if file_type in ["mp4", "avi", "mov", "mkv"]:
            return "视频"
        if file_type in ["zip", "rar", "7z", "exe", "msi", "dmg"]:
            return "安装包"
        if any(w in combined for w in ["方案", "solution", "proposal", "架构"]):
            return "方案"
        if any(w in combined for w in ["彩页", "宣传", "brochure", "介绍"]):
            return "彩页"
        return "方案"
    
    def detect_relations(self, file_tags: Dict[int, List[Dict]]) -> List[Tuple[int, int, str, float]]:
        """检测文件关系"""
        relations = []
        file_ids = list(file_tags.keys())
        
        for i, fid1 in enumerate(file_ids):
            tags1 = {t["value"] for t in file_tags[fid1]}
            for fid2 in file_ids[i+1:]:
                tags2 = {t["value"] for t in file_tags[fid2]}
                common = tags1 & tags2
                if len(common) >= 2:
                    confidence = len(common) / max(len(tags1), len(tags2))
                    relations.append((fid1, fid2, "related", confidence))
        return relations
