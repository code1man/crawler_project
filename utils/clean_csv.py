"""
CSV文件清理脚本
将resource目录下的CSV文件清理为只保留 keyword、url、user、comment_content 四列
并去除冗余信息
"""
import pandas as pd
import os
import re

def clean_url(url):
    """清理URL，去除token等参数"""
    if pd.isna(url) or not url:
        return ""
    # 只保留基本URL，去除token参数
    if '?' in url:
        base_url = url.split('?')[0]
        return base_url
    return url

def clean_comment(comment):
    """清理评论内容，去除日期、地点等冗余信息"""
    if pd.isna(comment) or not comment:
        return ""
    
    comment = str(comment).strip()
    
    # 移除HTML标签 如 <em>, </em> 等
    comment = re.sub(r'<[^>]+>', '', comment)
    
    # 移除末尾的 "回复" 字样
    comment = re.sub(r'\n*回复$', '', comment)
    
    # 移除日期格式 如 "11-12广东" "2024-03-15" "昨天 08:07澳大利亚"
    # 移除末尾的日期+地点
    comment = re.sub(r'\n\d{1,2}-\d{1,2}[^\n]*$', '', comment)
    comment = re.sub(r'\n\d{4}-\d{1,2}-\d{1,2}[^\n]*$', '', comment)
    comment = re.sub(r'\n昨天[^\n]*$', '', comment)
    comment = re.sub(r'\n今天[^\n]*$', '', comment)
    comment = re.sub(r'\n\d+天前[^\n]*$', '', comment)
    
    # 移除末尾的数字（点赞数）
    comment = re.sub(r'\n\d+$', '', comment)
    
    # 移除多余的换行
    comment = re.sub(r'\n+', ' ', comment)
    
    # 省份/地区列表
    provinces = '北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门|美国|英国|日本|韩国|澳大利亚|加拿大|新加坡|马来西亚|泰国|越南|印度|法国|德国|意大利|西班牙|俄罗斯|巴西'
    
    # 移除末尾的 "赞" 和 "回复" 标记
    comment = re.sub(r'\s*赞\s*$', '', comment)
    comment = re.sub(r'\s*回复\s*$', '', comment)
    
    # 移除末尾的地区信息
    comment = re.sub(rf'\s*({provinces})\s*$', '', comment)
    
    # 移除末尾常见的日期格式 如 "11-12", "11-12 09:30"
    comment = re.sub(r'\s*\d{1,2}-\d{1,2}(\s*\d{1,2}:\d{2})?\s*$', '', comment)
    
    # 移除 "昨天 11:02", "今天 09:30" 等格式
    comment = re.sub(r'\s*(昨天|今天|前天|刚刚|\d+分钟前|\d+小时前|\d+天前)\s*(\d{1,2}:\d{2})?\s*$', '', comment)
    
    # 再次移除可能残留的地区信息
    comment = re.sub(rf'\s*({provinces})\s*$', '', comment)

    return comment.strip()

def process_csv(input_file, output_file):
    """处理单个CSV文件"""
    print(f"正在处理: {input_file}")
    
    try:
        # 读取CSV，指定列名
        df = pd.read_csv(input_file, encoding='utf-8-sig')
        
        # 检查原始列名
        print(f"  原始列: {df.columns.tolist()}")
        print(f"  原始行数: {len(df)}")
        
        # 根据不同的列名映射
        result_rows = []
        
        for _, row in df.iterrows():
            # 尝试获取各字段
            keyword = row.get('keyword', '') or ''
            
            # URL可能在不同的列名
            url = row.get('note_url', '') or row.get('weibo_url', '') or row.get('url', '') or ''
            url = clean_url(url)
            
            # 用户名
            user = row.get('comment_user', '') or row.get('user_name', '') or ''
            
            # 评论内容
            comment = row.get('comment_content', '') or row.get('content', '') or ''
            comment = clean_comment(comment)
            
            # 跳过空评论或无效数据
            if not comment or len(comment) < 2:
                continue
            
            # 跳过URL为空的行
            if not url or 'search_result' in url:
                continue
                
            result_rows.append({
                'keyword': keyword,
                'url': url,
                'user': user,
                'comment_content': comment
            })
        
        # 创建新的DataFrame
        result_df = pd.DataFrame(result_rows)
        
        # 去重
        result_df = result_df.drop_duplicates(subset=['url', 'comment_content'])
        
        print(f"  清理后行数: {len(result_df)}")
        
        # 保存
        result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"  已保存到: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"  处理失败: {e}")
        return False

def main():
    resource_dir = "resource"
    
    # 获取所有CSV文件，排除已清理的文件
    csv_files = [f for f in os.listdir(resource_dir) if f.endswith('.csv') and '_clean' not in f]
    
    print(f"找到 {len(csv_files)} 个原始CSV文件")
    print("=" * 50)
    
    for csv_file in csv_files:
        input_path = os.path.join(resource_dir, csv_file)
        # 输出文件名加上 _clean 后缀（避免与旧文件冲突）
        output_name = csv_file.replace('.csv', '_clean.csv')
        output_path = os.path.join(resource_dir, output_name)
        
        process_csv(input_path, output_path)
        print()
    
    print("=" * 50)
    print("全部处理完成！")

if __name__ == "__main__":
    main()
