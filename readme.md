# Table Finder based on pdfplumber
- pdfplumber標準のtable検知アルゴリズムを、複雑な図表が多数含まれる教科書向けに変更を加えています。
- pdfplumberパッケージをこのリポジトリのものに置き換えて用いることを前提にしていましたが、table_filtering.pyとtable_filtering_utils.pyのみを独立して用いることも可能にする予定です。

## オリジナルとの変更点
- table.py, page.py, display.pyに存在する表検出関連のメソッドについて、AEMC用のもの(`*_AEMC()`)を追加しています。
- table_filtering.py, table_filtering_utils.pyが追加された.pyファイルです。table_filtering.pyは実際に表の選別をする処理を、table_filtering_utils.pyは表の選別処理を構成する、より一般的な処理を含んでいます。


## 処理内容
TODO