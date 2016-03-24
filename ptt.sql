-- --------------------------------------------------------

--
-- 資料表結構 `ptt_posts`
--

CREATE TABLE `ptt_posts` (
  `board` varchar(35) COLLATE utf8_unicode_ci NOT NULL,
  `url` varchar(25) COLLATE utf8_unicode_ci NOT NULL,
  `author` varchar(50) COLLATE utf8_unicode_ci NOT NULL,
  `title` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `datetime` datetime NOT NULL,
  `ip` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  `content` text COLLATE utf8_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- --------------------------------------------------------

--
-- 資料表結構 `ptt_pushes`
--

CREATE TABLE `ptt_pushes` (
  `url` varchar(25) COLLATE utf8_unicode_ci NOT NULL,
  `sno` int(11) NOT NULL,
  `status` char(1) COLLATE utf8_unicode_ci NOT NULL,
  `userid` varchar(35) COLLATE utf8_unicode_ci NOT NULL,
  `content` varchar(100) COLLATE utf8_unicode_ci NOT NULL,
  `datetime` varchar(35) COLLATE utf8_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- 已匯出資料表的索引
--

--
-- 資料表索引 `ptt_posts`
--
ALTER TABLE `ptt_posts`
  ADD PRIMARY KEY (`url`);

--
-- 資料表索引 `ptt_pushes`
--
ALTER TABLE `ptt_pushes`
  ADD KEY `url` (`url`);

--
-- 已匯出資料表的限制(Constraint)
--

--
-- 資料表的 Constraints `ptt_pushes`
--
ALTER TABLE `ptt_pushes`
  ADD CONSTRAINT `FK_url` FOREIGN KEY (`url`) REFERENCES `ptt_posts` (`url`) ON DELETE CASCADE ON UPDATE CASCADE;
