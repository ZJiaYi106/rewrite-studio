"""
测试脚本：验证磁盘清理功能
运行后检查 temp/jobs/ 目录，确认中间文件已被清理
"""
import os
from pathlib import Path

def check_cleanup_results():
    jobs_root = Path("temp/jobs")
    if not jobs_root.exists():
        print("❌ temp/jobs 目录不存在，无法检查")
        return
    
    job_dirs = list(jobs_root.iterdir())
    if not job_dirs:
        print("✅ 没有历史任务目录")
        return
    
    print(f"📁 发现 {len(job_dirs)} 个任务目录\n")
    
    total_before = 0
    total_after = 0
    
    for job_dir in job_dirs:
        if not job_dir.is_dir():
            continue
        
        parsed = job_dir / "parsed"
        processed = job_dir / "processed_images"
        output = job_dir / "output"
        original_images = output / "original_images" if output.exists() else None
        
        size_parsed = sum(f.stat().st_size for f in parsed.rglob("*") if f.is_file()) if parsed.exists() else 0
        size_processed = sum(f.stat().st_size for f in processed.rglob("*") if f.is_file()) if processed.exists() else 0
        size_original = sum(f.stat().st_size for f in original_images.rglob("*") if f.is_file()) if original_images and original_images.exists() else 0
        size_output = sum(f.stat().st_size for f in output.rglob("*") if f.is_file()) if output.exists() else 0
        
        should_cleanup = size_parsed + size_processed + size_original
        total_before += should_cleanup + size_output
        total_after += size_output
        
        status = "✅ 已清理" if should_cleanup == 0 else f"⚠️  待清理 {should_cleanup / 1024 / 1024:.2f} MB"
        print(f"  {job_dir.name}: {status}")
        if should_cleanup > 0:
            print(f"    - parsed: {size_parsed / 1024:.1f} KB")
            print(f"    - processed_images: {size_processed / 1024:.1f} KB")
            print(f"    - original_images: {size_original / 1024:.1f} KB")
    
    print(f"\n📊 统计：")
    print(f"  清理前总大小: {total_before / 1024 / 1024:.2f} MB")
    print(f"  清理后总大小: {total_after / 1024 / 1024:.2f} MB")
    print(f"  节省空间: {(total_before - total_after) / 1024 / 1024:.2f} MB ({(1 - total_after / max(total_before, 1)) * 100:.1f}%)")

if __name__ == "__main__":
    check_cleanup_results()
