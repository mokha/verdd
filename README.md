# Veʹrdd

[Veʹrdd](https://www.akusanat.com/verdd/ "Veʹrdd") is an open-source dictionary editing framework with the focus on
low-resourced and endangered languages. The framework is mainly built to
facilitate collecting, importing, editing and exporting dictionaries while
allowing the involvement of the native speakers to contribute easily to the
preservation of the language and construction of the dictionary.

The framework is built in Django and has a web-interface along with a list of
terminal commands such as exporting the information to Giella and Apertium XMLs,
and LaTeX.

![Screenshot of Veʹrdd](https://github.com/mokha/verdd/wiki/img/screenshot.png?raw=true "Screenshot of Veʹrdd")

## Features
Veʹrdd is rich in features, the main ones are:
- Ability to visually add, edit, annotate, approve and delete dictionary entries such as lexemes, stems, relations (e.g. translations) and mini-paradigms.
- Use of transducers and [UralicNLP](https://github.com/mikahama/uralicNLP "uralicNLP") to automatically generate mini-paradigms.
- Search and filter lexemes and relations.
- Bulk approve lexemes and relations.
- Logging all actions and reverting back to previous instances in case of an error.
- Link lexemes to external sources for further information.
- Automatically import dictionary entries from Giella's and Apertium's XML, LEXC and CSV files.
- Automatically export stored information in Veʹrdd in Giella's and Apertium's XML, LEXC and CSV formats.
- Automatically export a printable dictionary (in LaTeX).

For further information (e.g. installation, usages and localization), visit the [wiki](https://github.com/mokha/verdd/wiki).

## Contributors
- Khalid Alnajjar ([@mokha](https://github.com/mokha))
- Jack Rueter ([@rueter](https://github.com/rueter))
- Mika Hämäläinen ([@mikahama](https://github.com/mikahama))

## Publications
- Alnajjar, K., Hämäläinen, M., Rueter, J., & Partanen, N. (2020). [Ve’rdd. Narrowing the Gap between Paper Dictionaries, Low-Resource NLP and Community Involvement](https://www.researchgate.net/publication/346547635_Ve%27rdd_Narrowing_the_Gap_between_Paper_Dictionaries_Low-Resource_NLP_and_Community_Involvement). In M. Ptaszynski, & B. Ziolko (Eds.), Proceedings of the 28th International Conference on Computational Linguistics: System Demonstrations International Committee on Computational Linguistics.
- Alnajjar, K., Hämäläinen, M., & Rueter, J. (2020). [On Editing Dictionaries for Uralic Languages in an Online Environment](https://www.researchgate.net/publication/340254023_On_Editing_Dictionaries_for_Uralic_Languages_in_an_Online_Environment). In Proceedings of the Sixth International Workshop on Computational Linguistics of Uralic Languages (pp. 26–30). Stroudsburg, PA: The Association for Computational Linguistics.
- Alnajjar, K., Hämäläinen, M., Partanen, N., & Rueter, J. (2019). [The Open Dictionary Infrastructure for Uralic Languages](https://www.researchgate.net/publication/347930533_The_Open_Dictionary_Infrastructure_for_Uralic_Languages). In Электронная Письменность Народов Российской Федерации: Опыт, Проблемы И Перспективы (pp. 49-51). Ufa: Башкирская энциклопедия.
