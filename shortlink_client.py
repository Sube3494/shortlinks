"""
短链服务客户端 SDK
方便其他 Python 程序集成调用
"""
import requests
from typing import Optional, Dict, List


class ShortLinkClient:
    """短链服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            base_url: 短链服务的地址，例如: https://s.yourdomain.com
            api_key: API密钥（如果服务启用了认证）
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def shorten(self, url: str, custom_code: Optional[str] = None) -> Dict:
        """
        将长链接转换为短链接
        
        Args:
            url: 要缩短的长链接
            custom_code: 可选的自定义短码（6-10个字符）
        
        Returns:
            包含短链信息的字典，主要字段：
            - short_url: 完整的短链接（可直接使用）
            - short_code: 短码
            - original_url: 原始链接
        
        Example:
            >>> client = ShortLinkClient("https://s.yourdomain.com")
            >>> result = client.shorten("https://www.example.com/very/long/url")
            >>> print(result['short_url'])
            https://s.yourdomain.com/abc123
        """
        try:
            data = {"url": url}
            if custom_code:
                data["custom_code"] = custom_code
            
            response = requests.post(
                f"{self.api_url}/shorten",
                json=data,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"创建短链失败: {str(e)}")
    
    def get_info(self, short_code: str) -> Dict:
        """获取短链详细信息"""
        try:
            response = requests.get(
                f"{self.api_url}/info/{short_code}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取短链信息失败: {str(e)}")
    
    def get_stats(self, short_code: str) -> Dict:
        """获取短链统计信息"""
        try:
            response = requests.get(
                f"{self.api_url}/stats/{short_code}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取统计信息失败: {str(e)}")
    
    def delete(self, short_code: str) -> Dict:
        """删除短链"""
        try:
            response = requests.delete(
                f"{self.api_url}/{short_code}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"删除短链失败: {str(e)}")
    
    def list_all(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """列出所有短链"""
        try:
            response = requests.get(
                f"{self.api_url}/list",
                params={"skip": skip, "limit": limit},
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取短链列表失败: {str(e)}")


# 使用示例
if __name__ == "__main__":
    # 初始化客户端（替换为你的域名）
    client = ShortLinkClient("https://s.yourdomain.com")
    
    # 示例1: 将长链接转换为短链接
    long_url = "https://www.example.com/very/long/url/path/with/many/parameters"
    result = client.shorten(long_url)
    print(f"原始链接: {long_url}")
    print(f"短链接: {result['short_url']}")
    print(f"短码: {result['short_code']}")
    
    # 示例2: 使用自定义短码
    custom_result = client.shorten("https://www.github.com", custom_code="github")
    print(f"\n自定义短码短链接: {custom_result['short_url']}")
    
    # 示例3: 获取短链统计
    stats = client.get_stats(result['short_code'])
    print(f"\n点击次数: {stats['click_count']}")

