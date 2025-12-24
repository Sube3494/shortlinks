#!/usr/bin/env python3
"""
API Key 管理命令行工具

使用方法:
    python manage_keys.py create --name "密钥名称" [--expires-days 90]
    python manage_keys.py list
    python manage_keys.py info <key_id>
    python manage_keys.py update <key_id> --name "新名称" [--expires-days 180]
    python manage_keys.py revoke <key_id>
    python manage_keys.py delete <key_id> --confirm
"""

import argparse
import secrets
import sys
from datetime import datetime, timedelta
from typing import Optional

# 导入数据库相关模块
from database import SessionLocal, APIKey, ShortLink, init_db


def generate_api_key() -> str:
    """生成安全的 API Key"""
    return secrets.token_urlsafe(48)


def format_datetime(dt: Optional[datetime]) -> str:
    """格式化日期时间"""
    if not dt:
        return "Never"
    
    now = datetime.now()
    diff = now - dt
    
    if diff.total_seconds() < 60:
        return "刚刚"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes}分钟前"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}小时前"
    elif diff.total_seconds() < 604800:
        days = int(diff.total_seconds() / 86400)
        return f"{days}天前"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def format_expires(dt: Optional[datetime]) -> str:
    """格式化过期时间"""
    if not dt:
        return "Never"
    
    now = datetime.now()
    if now > dt:
        return f"已过期 ({dt.strftime('%Y-%m-%d')})"
    else:
        return dt.strftime("%Y-%m-%d")


def create_key(args):
    """创建新的 API Key"""
    db = SessionLocal()
    try:
        # 生成新密钥
        key = generate_api_key()
        
        # 计算过期时间
        expires_at = None
        if args.expires_days and args.expires_days > 0:
            expires_at = datetime.now() + timedelta(days=args.expires_days)
        
        # 创建数据库记录
        api_key = APIKey(
            key=key,
            name=args.name,
            expires_at=expires_at
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        print(f"\n✅ API Key 创建成功!")
        print(f"\nID: {api_key.id}")
        print(f"名称: {api_key.name}")
        print(f"密钥: {api_key.key}")
        print(f"创建时间: {api_key.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if expires_at:
            print(f"过期时间: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"过期时间: 永不过期")
        
        print(f"\n⚠️  请妥善保存上述密钥,它只会显示一次!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 创建失败: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def list_keys(args):
    """列出所有 API Keys"""
    db = SessionLocal()
    try:
        # 查询所有活跃的 Key
        keys = db.query(APIKey).filter(APIKey.is_active == True).order_by(APIKey.created_at.desc()).all()
        
        if not keys:
            print("\n📭 暂无活跃的 API Keys")
            return
        
        print(f"\n🔑 共有 {len(keys)} 个活跃的 API Keys:\n")
        print(f"{'ID':<5} {'名称':<20} {'密钥前缀':<15} {'过期时间':<15} {'最后使用':<20} {'使用次数':<10}")
        print("-" * 95)
        
        for key in keys:
            key_prefix = key.key[:12] + "..." if len(key.key) > 12 else key.key
            last_used = format_datetime(key.last_used_at)
            expires = format_expires(key.expires_at)
            
            print(f"{key.id:<5} {key.name:<20} {key_prefix:<15} {expires:<15} {last_used:<20} {key.usage_count:<10}")
        
        print()
        
    finally:
        db.close()


def info_key(args):
    """查看 API Key 详细信息"""
    db = SessionLocal()
    try:
        key = db.query(APIKey).filter(APIKey.id == args.key_id).first()
        
        if not key:
            print(f"\n❌ Key ID {args.key_id} 不存在")
            sys.exit(1)
        
        print(f"\n📋 API Key 详细信息:\n")
        print(f"ID: {key.id}")
        print(f"名称: {key.name}")
        print(f"密钥: {key.key[:12]}... (出于安全考虑,仅显示前缀)")
        print(f"状态: {'✅ 活跃' if key.is_active else '❌ 已撤销'}")
        print(f"创建时间: {key.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if key.expires_at:
            status = "已过期" if datetime.now() > key.expires_at else "有效"
            print(f"过期时间: {key.expires_at.strftime('%Y-%m-%d %H:%M:%S')} ({status})")
        else:
            print(f"过期时间: 永不过期")
        
        if key.last_used_at:
            print(f"最后使用: {key.last_used_at.strftime('%Y-%m-%d %H:%M:%S')} ({format_datetime(key.last_used_at)})")
        else:
            print(f"最后使用: 从未使用")
        
        print(f"使用次数: {key.usage_count}")
        print()
        
    finally:
        db.close()


def update_key(args):
    """更新 API Key 信息"""
    db = SessionLocal()
    try:
        key = db.query(APIKey).filter(APIKey.id == args.key_id).first()
        
        if not key:
            print(f"\n❌ Key ID {args.key_id} 不存在")
            sys.exit(1)
        
        # 更新名称
        if args.name:
            old_name = key.name
            key.name = args.name
            print(f"✅ 名称已更新: {old_name} -> {args.name}")
        
        # 更新过期时间
        if args.expires_days is not None:
            if args.expires_days > 0:
                key.expires_at = datetime.now() + timedelta(days=args.expires_days)
                print(f"✅ 过期时间已设置为: {key.expires_at.strftime('%Y-%m-%d')}")
            else:
                key.expires_at = None
                print(f"✅ 已设置为永不过期")
        
        db.commit()
        print(f"\n✅ Key ID {args.key_id} 更新成功!\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 更新失败: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def revoke_key(args):
    """撤销 API Key"""
    db = SessionLocal()
    try:
        key = db.query(APIKey).filter(APIKey.id == args.key_id).first()
        
        if not key:
            print(f"\n❌ Key ID {args.key_id} 不存在")
            sys.exit(1)
        
        if not key.is_active:
            print(f"\n⚠️  Key ID {args.key_id} 已经被撤销")
            return
        
        key.is_active = False
        db.commit()
        
        print(f"\n✅ Key ID {args.key_id} ('{key.name}') 已成功撤销")
        print(f"该密钥将立即失效,无法再用于 API 调用\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 撤销失败: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def delete_key(args):
    """物理删除 API Key"""
    if not args.confirm:
        print("\n⚠️  警告: 删除操作不可恢复!")
        print("请使用 --confirm 参数确认删除操作")
        sys.exit(1)
    
    db = SessionLocal()
    try:
        key = db.query(APIKey).filter(APIKey.id == args.key_id).first()
        
        if not key:
            print(f"\n❌ Key ID {args.key_id} 不存在")
            sys.exit(1)
        
        key_name = key.name
        db.delete(key)
        db.commit()
        
        print(f"\n✅ Key ID {args.key_id} ('{key_name}') 已永久删除\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 删除失败: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def cleanup_expired(args):
    """清理过期 Key 的数据"""
    db = SessionLocal()
    try:
        now = datetime.now()
        
        # 查找所有过期的 Key
        expired_keys = db.query(APIKey).filter(
            APIKey.expires_at != None,
            APIKey.expires_at < now
        ).all()
        
        if not expired_keys:
            print("\n✅ 没有过期的 Key 需要清理")
            return
        
        print(f"\n🔍 发现 {len(expired_keys)} 个过期的 Key\n")
        
        total_deleted = 0
        for key in expired_keys:
            # 统计该 Key 创建的短链数量
            link_count = db.query(ShortLink).filter(
                ShortLink.created_by_key_id == key.id
            ).count()
            
            # 删除该 Key 创建的所有短链
            deleted_count = db.query(ShortLink).filter(
                ShortLink.created_by_key_id == key.id
            ).delete()
            
            # 撤销 Key
            key.is_active = False
            
            print(f"🗑️  Key '{key.name}' (ID: {key.id})")
            print(f"   过期时间: {key.expires_at.strftime('%Y-%m-%d %H:%M')}")
            print(f"   清理短链: {deleted_count} 条")
            print()
            
            total_deleted += deleted_count
        
        db.commit()
        print(f"✅ 清理完成! 共删除 {total_deleted} 条短链\n")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 清理失败: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def main():
    """主函数"""
    # 确保数据库已初始化
    init_db()
    
    parser = argparse.ArgumentParser(
        description="API Key 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # create 命令
    create_parser = subparsers.add_parser('create', help='创建新的 API Key')
    create_parser.add_argument('--name', required=True, help='Key 名称/备注')
    create_parser.add_argument('--expires-days', type=int, help='过期天数(0 或不设置表示永不过期)')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有活跃的 API Keys')
    
    # info 命令
    info_parser = subparsers.add_parser('info', help='查看 API Key 详细信息')
    info_parser.add_argument('key_id', type=int, help='Key ID')
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='更新 API Key')
    update_parser.add_argument('key_id', type=int, help='Key ID')
    update_parser.add_argument('--name', help='新的名称')
    update_parser.add_argument('--expires-days', type=int, help='新的过期天数(0 表示永不过期)')
    
    # revoke 命令
    revoke_parser = subparsers.add_parser('revoke', help='撤销 API Key')
    revoke_parser.add_argument('key_id', type=int, help='Key ID')
    
    # delete 命令
    delete_parser = subparsers.add_parser('delete', help='永久删除 API Key')
    delete_parser.add_argument('key_id', type=int, help='Key ID')
    delete_parser.add_argument('--confirm', action='store_true', help='确认删除')
    
    # cleanup 命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理过期 Key 的数据')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行对应命令
    commands = {
        'create': create_key,
        'list': list_keys,
        'info': info_key,
        'update': update_key,
        'revoke': revoke_key,
        'delete': delete_key,
        'cleanup': cleanup_expired
    }
    
    commands[args.command](args)


if __name__ == '__main__':
    main()
