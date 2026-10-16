"""
手动清理脚本：清理历史任务的中间文件
适用于已经完成的旧任务
"""
import shutil
from pathlib import Path

def cleanup_historical_jobs():
    jobs_root = Path("temp/jobs")
    if not jobs_root.exists():
        print("✅ temp/jobs 目录不存在，无需清理")
        return
    
    job_dirs = [d for d in jobs_root.iterdir() if d.is_dir()]
    if not job_dirs:
        print("✅ 没有历史任务目录")
        return
    
    print(f"🔍 扫描 {len(job_dirs)} 个任务目录...\n")
    
    total_cleaned = 0
    cleaned_count = 0
    
    for job_dir in job_dirs:
        job_cleaned = 0
        
        # 清理 parsed 目录
        parsed = job_dir / "parsed"
        if parsed.exists():
            size = sum(f.stat().st_size for f in parsed.rglob("*") if f.is_file())
            shutil.rmtree(parsed, ignore_errors=True)
            job_cleaned += size
        
        # 清理 processed_images 目录
        processed = job_dir / "processed_images"
        if processed.exists():
            size = sum(f.stat().st_size for f in processed.rglob("*") if f.is_file())
            shutil.rmtree(processed, ignore_errors=True)
            job_cleaned += size
        
        # 清理 output/original_images 目录
        output = job_dir / "output"
        if output.exists():
            original_images = output / "original_images"
            if original_images.exists():
                size = sum(f.stat().st_size for f in original_images.rglob("*") if f.is_file())
                shutil.rmtree(original_images, ignore_errors=True)
                job_cleaned += size
        
        # 清理 ZIP 文件
        for zip_file in job_dir.glob("rewrite-*.zip"):
            job_cleaned += zip_file.stat().st_size
            zip_file.unlink(missing_ok=True)
        
        if job_cleaned > 0:
            print(f"  清理 {job_dir.name}: {job_cleaned / 1024 / 1024:.2f} MB")
            total_cleaned += job_cleaned
            cleaned_count += 1
    
    print(f"\n✅ 完成！")
    print(f"  处理任务数: {cleaned_count}/{len(job_dirs)}")
    print(f"  释放空间: {total_cleaned / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    import sys
    
    print("⚠️  此脚本将清理所有历史任务的中间文件")
    print("   保留：output/article.md 和 output/images/")
    print("   删除：parsed/, processed_images/, original_images/, *.zip\n")
    
    if "--yes" not in sys.argv:
        confirm = input("确认执行清理？(输入 yes 继续): ").strip().lower()
        if confirm != "yes":
            print("❌ 已取消")
            sys.exit(0)
    
    cleanup_historical_jobs()
