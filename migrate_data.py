'''
Date: 2025-12-24 15:32:59
Author: Sube
FilePath: migrate_data.py
LastEditTime: 2025-12-24 15:37:29
Description: 
'''
#!/usr/bin/env python3
"""
数据迁移脚本: 为现有短链分配默认 Key

运行方式:
    python migrate_data.py
"""

import secrets
from sqlalchemy import text
from database import SessionLocal, ShortLink, APIKey, init_db, engine


def upgrade_database():
    """升级数据库结构：添加新列"""
    print("\n🔧 检查数据库结构...")
    
    # 直接使用原生 SQL 检查和添加列
    with engine.connect() as conn:
        # 检查列是否已存在
        result = conn.execute(text("PRAGMA table_info(shortlinks)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'created_by_key_id' not in columns:
            print("📝 添加 created_by_key_id 列...")
            # SQLite 添加列
            conn.execute(text(
                "ALTER TABLE shortlinks ADD COLUMN created_by_key_id INTEGER"
            ))
            conn.commit()
            print("✅ 数据库结构已更新")
        else:
            print("✅ 数据库结构已是最新")


def migrate_existing_links():
    """为现有的未分配短链创建系统 Key 并关联"""
    # 先升级数据库结构
    upgrade_database()
    
    # 初始化数据库（确保 api_keys 表存在）
    init_db()
    
    db = SessionLocal()
    try:
        # 查找所有未分配的短链
        orphan_links = db.query(ShortLink).filter(
            ShortLink.created_by_key_id == None
        ).all()
        
        if not orphan_links:
            print("✅ 无需迁移，所有短链已分配创建者")
            return
        
        print(f"\n📋 发现 {len(orphan_links)} 条未分配的短链")
        
        # 查找或创建"系统迁移" Key
        system_key = db.query(APIKey).filter(APIKey.name == "系统迁移").first()
        
        if not system_key:
            print("\n🔧 创建系统迁移 Key...")
            system_key = APIKey(
                key=secrets.token_urlsafe(48),
                name="系统迁移",
                is_active=True
            )
            db.add(system_key)
            db.commit()
            db.refresh(system_key)
            
            print(f"✅ 系统 Key 已创建 (ID: {system_key.id})")
            print(f"   密钥: {system_key.key}")
            print(f"   说明: 此 Key 用于管理迁移前创建的所有短链")
        else:
            print(f"\n✅ 使用现有系统 Key (ID: {system_key.id})")
        
        # 分配所有未分配的短链
        print(f"\n🔄 正在分配短链...")
        for link in orphan_links:
            link.created_by_key_id = system_key.id
        
        db.commit()
        
        print(f"✅ 迁移完成! 已将 {len(orphan_links)} 条短链分配给系统 Key")
        print(f"\n💡 提示: 使用以下命令查看系统 Key:")
        print(f"   python manage_keys.py info {system_key.id}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 迁移失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    print("=" * 60)
    print("数据迁移: 为现有短链分配创建者")
    print("=" * 60)
    migrate_existing_links()
    print("\n" + "=" * 60)
