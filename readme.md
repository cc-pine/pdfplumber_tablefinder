# Table Finder based on pdfplumber
- pdfplumber標準のtable検知アルゴリズムを、複雑な図表が多数含まれる教科書向けに変更を加えています。
- pdfplumberパッケージをこのリポジトリのものに置き換えて用いることを前提にしていましたが、table_filtering.pyとtable_filtering_utils.pyのみを独立して用いることも可能にする予定です。

## オリジナルとの変更点
- table.py, page.py, display.pyに存在する表検出関連のメソッドについて、AEMC用のもの(`.*_2()`)を追加しています。
- table.pyの中のAEMC用に作成した`TableFinder2`クラスでは、エッジの抽出方法の変更・テーブル抽出処理の変更がなされています。
- utils.pyには、いくつかの一般的な処理を追加しています。
- table_filtering.py,、table_filtering_utils.py、debug_drawer.pyが追加された.pyファイルです。table_filtering.pyは実際に表の選別をする処理を、table_filtering_utils.pyは表の選別処理を構成する、より一般的な処理を含んでいます。debug_drawer.pyには、デバッグ用のコード（table_finder2()の結果図示、bounding boxのpdf.page上への描画）が含まれます。
- cli.py、container.py、convert.py、pdf.pyにはオリジナルからの変更はありません。


## 処理内容の詳細
- エッジ抽出の改善(`table.TableFinder2.get_edges()`)
  `table.merge_edges_aemc`を使用。
  - ページ端に達するエッジの除去、ページ全域に渡るエッジの除去を実施
  - snap -> mergeではなく merge -> snapとするように変更
- 不要なセルの除去(`table_filtering.remove_.*_cells()`)
  - 文字よりも小さいセルの除去
  - 他のセルより極端に高さの低いものを除去

- 不要なテーブルの除去（`table_filtering.remove.*tables.*()`）
  - 文字を含まないもの
  - 文字を含む矩形+文字を含まない矩形となっているもの
  - 構成するセルの高さ and 幅がすべて異なるもの
  - 矩形で囲まれた文字の集合
  - 周辺の文字サイズより小さいセルを多数含むもの
  - 文字を含まないセルが多いもの
  - セルに1文字ずつしか含まれていないもの
  - セルの数 > 矩形のnon-stroking-colorの数であるもの
  - セルが近接しているだけで整列していないもの
  - 矩形同士の距離の制約