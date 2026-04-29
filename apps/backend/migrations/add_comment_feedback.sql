-- 评审评论增加用户反馈字段
ALTER TABLE review_comments ADD COLUMN IF NOT EXISTS feedback VARCHAR(16);
